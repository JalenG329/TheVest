import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2
import numpy as np
import time

import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
from threading import Thread

# Initialize I2C and haptic driver
I2C = busio.I2C(board.SCL, board.SDA)
MUX = adafruit_tca9548a.TCA9548A(I2C)
DRV = DRV2605(MUX[3])

# Configuration
PRINT_INTERVAL = 0.1
SCALE = (224/1280, 224/720)  # (x_scale, y_scale)
DEPTH_HISTORY_SIZE = 3
DEPTH_CHANGE_THRESHOLD = 15
FOCAL_LENGTH_MM = 4.74  # Camera focal length in mm
IMAGE_HEIGHT = 720  # Assuming 720p input

# Global state
last_print_time = 0
tracked_objects = {}
next_track_id = 1
depth_history = {}


def vibrate_motor(depth_value, min_depth=100, max_depth=800, min_v=0, max_v=127):
    """Vibrate motor based on depth value."""
    DRV.mode = MODE_REALTIME

    def map_depth_to_vibrator(depth, min_d, max_d, min_v, max_v):
        if max_d == min_d:
            return min_v
        # Invert mapping: closer object (smaller depth) = higher vibration
        if depth <= min_d:
            return max_v
        elif depth >= max_d:
            return min_v
        else:
            return int(max_v - (depth - min_d) * (max_v - min_v) / (max_d - min_d))

    # Clamp and scale: closer object = higher vibration (127=max, 0=min)
    mapped_value = map_depth_to_vibrator(depth_value, min_depth, max_depth, min_v, max_v)
    mapped_value = max(min_v, min(max_v, mapped_value))  # Clamp to 0-127
    print(f"Simulated depth: {depth_value:.2f}, Vibration value: {mapped_value}")
    DRV.realtime_value = mapped_value
    time.sleep(1)
    DRV.realtime_value = 0
    DRV.mode = MODE_INTTRIG

def init_models():
    """Initialize and return combined detection model."""
    detection_model = dg.load_model("yolov8m_coco--640x640_quant_hailort_hailo8_1", "@local", 
                                   "/home/rohan/degirum_wearable_device/models")
    nav_model = dg.load_model("ubuntu--640x640_quant_hailort_hailo8_1", "@local",
                             "/home/rohan/degirum_wearable_device/models")
    return CombiningCompoundModel(detection_model, nav_model)

def stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf):
    if (prev_gray is not None and prev_des is not None and des is not None 
        and len(prev_kp) > 0 and len(kp) > 0):
        matches = bf.match(prev_des, des)
        if len(sorted(matches, key=lambda x: x.distance)) > 200:
            src_pts = np.float32([prev_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            m, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC)
            if m is not None:
                return cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), 
                                    flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    return frame

def calculate_iou(box1, box2):
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    inter_x_min, inter_y_min = max(x1_min, x2_min), max(y1_min, y2_min)
    inter_x_max, inter_y_max = min(x1_max, x2_max), min(y1_max, y2_max)
    if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
        return 0.0
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    return inter_area / (box1_area + box2_area - inter_area)

def update_tracked_objects(detections):
    global tracked_objects, next_track_id, depth_history
    new_tracked_objects, used_track_ids = {}, set()
    for detection in detections:
        bbox, label = detection['bbox'], detection['label']
        best_match_id, best_iou = None, 0
        for track_id, tracked_obj in tracked_objects.items():
            if tracked_obj['label'] == label:
                iou = calculate_iou(bbox, tracked_obj['bbox'])
                if iou > best_iou and iou > 0.3:
                    best_iou, best_match_id = iou, track_id
        track_id = (best_match_id if best_match_id and best_match_id not in used_track_ids 
                   else next_track_id)
        if track_id == next_track_id:
            next_track_id += 1
        else:
            used_track_ids.add(track_id)
        new_tracked_objects[track_id] = {
            'bbox': bbox, 'label': label, 'last_seen': time.time(),
            'is_new': track_id not in tracked_objects
        }
    current_time = time.time()
    tracked_objects = {k: v for k, v in new_tracked_objects.items() 
                      if current_time - v.get('last_seen', 0) < 2.0}
    depth_history = {k: v for k, v in depth_history.items() if k in tracked_objects}
    return new_tracked_objects

def process_depth(track_id, depth_value, is_new_object):
    global depth_history
    if track_id not in depth_history:
        depth_history[track_id] = []
    depth_history[track_id].append(depth_value)
    if len(depth_history[track_id]) > DEPTH_HISTORY_SIZE:
        depth_history[track_id] = depth_history[track_id][-DEPTH_HISTORY_SIZE:]
    avg_depth = np.mean(depth_history[track_id])
    should_print = is_new_object
    if not is_new_object and len(depth_history[track_id]) >= 2:
        prev_avg = np.mean(depth_history[track_id][:-1])
        should_print = abs(avg_depth - prev_avg) > DEPTH_CHANGE_THRESHOLD
    return avg_depth, should_print

def simulate_depth(bbox, focal_length_mm=FOCAL_LENGTH_MM, image_height=IMAGE_HEIGHT, real_object_height_mm=150):
    # Simulate depth: depth = (real_object_height * focal_length) / bbox_height
    y_min, y_max = bbox[1], bbox[3]
    bbox_height = max(1, y_max - y_min)
    depth = (real_object_height_mm * focal_length_mm * image_height) / (bbox_height * 4.8)  # 4.8mm sensor height typical for Pi Cam
    return depth

def main():
    global last_print_time, tracked_objects
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
    camera.start()
    combined_model = init_models()
    orb = cv2.ORB_create(2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    prev_gray = prev_kp = prev_des = None
    with degirum_tools.Display("Detection to Depth Camera (Simulated)") as output_display:
        while True:
            frame = camera.capture_array("main")
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            kp, des = orb.detectAndCompute(gray, None)
            stabilized_frame = stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf)
            result = combined_model.predict(stabilized_frame)
            current_time = time.time()
            should_print = current_time - last_print_time >= PRINT_INTERVAL
            tracked_objects = update_tracked_objects(result._inference_results)
            if should_print:
                last_print_time = current_time
                for track_id, obj in tracked_objects.items():
                    bbox, label, is_new = obj['bbox'], obj['label'], obj.get('is_new', False)
                    # Simulate depth using bbox height
                    center_depth = simulate_depth(bbox)
                    avg_depth, should_print_depth = process_depth(track_id, center_depth, is_new)
                    if should_print_depth and label:
                        status = "NEW" if is_new else "UPDATED"
                        print(f"Track ID {track_id} - {label} ({status}): depth {avg_depth:.2f} (simulated)")
                    if label in ["cell phone", "remote"]:
                        vibrate_thread = Thread(target=vibrate_motor, args=(float(center_depth),))
                        vibrate_thread.start()
                    obj['is_new'] = False
            output_display.show(result)
            prev_gray, prev_kp, prev_des = gray, kp, des

if __name__ == "__main__":
    main()
