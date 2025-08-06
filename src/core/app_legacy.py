import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2
import numpy as np
import time

import board
import busio
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
from threading import Thread

# Initialize I2C and haptic driver
I2C = busio.I2C(board.SCL, board.SDA)
DRV = DRV2605(I2C)

# Configuration
SCALE = (224/1280, 224/720)  # (x_scale, y_scale)
DEPTH_HISTORY_SIZE = 3
DEPTH_CHANGE_THRESHOLD = 15

# Global state
last_print_time = 0
tracked_objects = {}
next_track_id = 1
depth_history = {}

def vibrate_motor(depth_value, min_depth=18.91, max_depth=79.79, min_v=0, max_v=127):
    """Vibrate motor based on depth value."""
    DRV.mode = MODE_REALTIME

    # Map depth value to a range suitable for vibration intensity
    def map_depth_to_vibrator(depth, min_d, max_d, min_v, max_v):
        if max_d == min_d:
            return min_v
        return int(min_v + (depth - min_d) * (max_v - min_v) / (max_d - min_d))

    mapped_value = map_depth_to_vibrator(depth_value, min_depth, max_depth, min_v, max_v)
    DRV.realtime_value = mapped_value
    # Removed time.sleep and reset to 0 for continuous vibration
    # DRV.mode = MODE_INTTRIG

def init_models():
    """Initialize and return combined detection model and depth model."""
    detection_model = dg.load_model("yolov8m_coco--640x640_quant_hailort_hailo8_1", "@local", 
                                   "/home/rohan/degirum_wearable_device/models")
    nav_model = dg.load_model("ubuntu--640x640_quant_hailort_hailo8_1", "@local",
                             "/home/rohan/degirum_wearable_device/models")
    depth_model = dg.load_model("depth_anything_v2--224x224_quant_hailort_hailo8_1", "@local",
                               "/home/rohan/degirum_wearable_device/models")
    return CombiningCompoundModel(detection_model, nav_model), depth_model

def stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf):
    """Apply ORB-based stabilization if possible, otherwise return original frame."""
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
    """Calculate IoU between two bounding boxes."""
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
    """Update tracked objects with new detections."""
    global tracked_objects, next_track_id, depth_history
    
    new_tracked_objects, used_track_ids = {}, set()
    
    for detection in detections:
        bbox, label = detection['bbox'], detection['label']
        best_match_id, best_iou = None, 0
        
        # Find best matching tracked object
        for track_id, tracked_obj in tracked_objects.items():
            if tracked_obj['label'] == label:
                iou = calculate_iou(bbox, tracked_obj['bbox'])
                if iou > best_iou and iou > 0.3:
                    best_iou, best_match_id = iou, track_id
        
        # Assign track ID
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
    
    # Clean up old objects and depth history
    current_time = time.time()
    tracked_objects = {k: v for k, v in new_tracked_objects.items() 
                      if current_time - v.get('last_seen', 0) < 2.0}
    depth_history = {k: v for k, v in depth_history.items() if k in tracked_objects}
    
    return new_tracked_objects


def main():
    global last_print_time, tracked_objects

    # Initialize camera and models
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
    camera.start()
    
    combined_model, depth_model = init_models()
    orb = cv2.ORB_create(2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    prev_gray = prev_kp = prev_des = None

    with degirum_tools.Display("Detection to Depth Camera") as output_display:
        while True:
            
            frame = camera.capture_array("main")
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            kp, des = orb.detectAndCompute(gray, None)

            # Stabilize frame
            stabilized_frame = stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf)

            # Run detection
            result = combined_model.predict(stabilized_frame)
            tracked_objects = update_tracked_objects(result._inference_results)
            depth_result = depth_model.predict(stabilized_frame)
            depth_map = depth_result._inference_results[0]['data'].reshape((224, 224))



            for track_id, obj in tracked_objects.items():
                bbox, label, is_new = obj['bbox'], obj['label'], obj.get('is_new', False)
                
                # Scale bbox coordinates to depth map size
                x_min = max(0, min(int(bbox[0] * SCALE[0]), 223))
                y_min = max(0, min(int(bbox[1] * SCALE[1]), 223))
                x_max = max(0, min(int(bbox[2] * SCALE[0]), 223))
                y_max = max(0, min(int(bbox[3] * SCALE[1]), 223))
                
                # Get depth at center of bbox
                center_depth = depth_map[(y_min + y_max) // 2, (x_min + x_max) // 2]

                # Get average depth of bounding box
                average_depth = np.mean(depth_map[y_min:y_max, x_min:x_max])
                
                # Vibrate motor if label is "cell phone" or "remote"
                if label in ["cell phone", "remote"]:
                    vibrate_motor(float(average_depth))
                obj['is_new'] = False
            # After processing all objects, turn off vibration if no relevant object is detected
            if not any(obj['label'] in ["cell phone", "remote"] for obj in tracked_objects.values()):
                DRV.realtime_value = 0
            output_display.show(result)
            prev_gray, prev_kp, prev_des = gray, kp, des

if __name__ == "__main__":
    main()
