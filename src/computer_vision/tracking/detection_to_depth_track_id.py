import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import collections
import time

last_print_time = 0
print_interval = .2  # seconds

xscale = 224 / 1280  # Width
yscale = 224 / 720   # Height

# Define obstacles that are relevant for walking navigation
WALKING_OBSTACLES = {'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 'traffic light', 
                    'fire hydrant', 'stop sign', 'parking meter', 'bench', 'chair', 'potted plant',
                    'dining table', 'couch', 'bed', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
                    'keyboard', 'cell phone', 'microwave', 'oven', 'sink', 'refrigerator',
                    'book', 'clock', 'vase'}

# Global tracking variables
tracked_objects = {}
next_track_id = 1
depth_history = {}  # Track depth history for each object
DEPTH_HISTORY_SIZE = 3
DEPTH_CHANGE_THRESHOLD = 15

# Init camera
def init_camera():
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    camera.set_controls({
        "FrameRate": 5})  # Target framerate
    camera.start()
    return camera

# Init models
def load_models():
    detection_model = dg.load_model(
        model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
        inference_host_address="@local",
        zoo_url="/home/rohan/degirum_wearable_device/models"
    )
    depth_model = dg.load_model(
        model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
        inference_host_address="@local",
        zoo_url="/home/rohan/degirum_wearable_device/models"
    )
    return detection_model, depth_model

# ORB-based video stabilization setup
def stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf, min_matches=200):
    if prev_gray is not None and prev_des is not None and des is not None and len(prev_kp) > 0 and len(kp) > 0:
        matches = bf.match(prev_des, des)
        matches = sorted(matches, key=lambda x: x.distance)
        if len(matches) > min_matches:
            src_pts = np.float32([prev_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            m, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC)
            if m is not None:
                stabilized_frame = cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
                return stabilized_frame
    return frame

def calculate_iou(box1, box2):
    """Calculate Intersection over Union (IoU) of two bounding boxes."""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # Calculate intersection coordinates
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    # Calculate intersection area
    if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
        return 0.0
    
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    
    # Calculate union area
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0.0

def update_tracked_objects(detections, iou_threshold=0.3):
    """Update tracked objects with new detections."""
    global tracked_objects, next_track_id
    
    # Filter detections to only include walking obstacles
    obstacle_detections = [det for det in detections if det['label'] in WALKING_OBSTACLES]
    
    new_tracked_objects = {}
    used_track_ids = set()
    
    for detection in obstacle_detections:
        bbox = detection['bbox']
        label = detection['label']
        
        best_match_id = None
        best_iou = 0
        
        # Find best matching tracked object
        for track_id, tracked_obj in tracked_objects.items():
            if tracked_obj['label'] == label:  # Only match same label
                iou = calculate_iou(bbox, tracked_obj['bbox'])
                if iou > best_iou and iou > iou_threshold:
                    best_iou = iou
                    best_match_id = track_id
        
        # Assign track ID
        if best_match_id is not None and best_match_id not in used_track_ids:
            track_id = best_match_id
            used_track_ids.add(track_id)
        else:
            track_id = next_track_id
            next_track_id += 1
        
        new_tracked_objects[track_id] = {
            'bbox': bbox,
            'label': label,
            'last_seen': time.time(),
            'is_new': track_id not in tracked_objects  # Mark if this is a new object
        }
    
    # Remove old tracked objects (not seen for more than 2 seconds)
    current_time = time.time()
    tracked_objects = {k: v for k, v in new_tracked_objects.items() 
                      if current_time - v.get('last_seen', 0) < 2.0}
    
    # Clean up depth history for removed objects
    global depth_history
    depth_history = {k: v for k, v in depth_history.items() if k in tracked_objects}
    
    return new_tracked_objects

def update_depth_history(track_id, depth_value):
    """Update depth history for an object and return the averaged depth."""
    global depth_history
    
    if track_id not in depth_history:
        depth_history[track_id] = []
    
    # Add new depth value
    depth_history[track_id].append(depth_value)
    
    # Keep only the last DEPTH_HISTORY_SIZE values
    if len(depth_history[track_id]) > DEPTH_HISTORY_SIZE:
        depth_history[track_id] = depth_history[track_id][-DEPTH_HISTORY_SIZE:]
    
    # Return averaged depth
    return np.mean(depth_history[track_id])

def should_print_depth(track_id, current_avg_depth, is_new_object):
    """Determine if we should print the depth based on change threshold."""
    if is_new_object:
        return True
    
    # Check if we have enough history to compare
    if track_id in depth_history and len(depth_history[track_id]) >= 2:
        # Get previous averaged depth (without current reading)
        prev_readings = depth_history[track_id][:-1]
        if len(prev_readings) > 0:
            prev_avg_depth = np.mean(prev_readings)
            depth_change = abs(current_avg_depth - prev_avg_depth)
            return depth_change > DEPTH_CHANGE_THRESHOLD
    
    return False


def main():
    global last_print_time, tracked_objects, depth_history
    camera = init_camera()
    detection_model, depth_model = load_models()
    orb = cv2.ORB_create(2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    prev_gray = None
    prev_kp = None
    prev_des = None

    with degirum_tools.Display("Detection to Depth Camera") as output_display:
        while True:
            frame = camera.capture_array("main")
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            kp, des = orb.detectAndCompute(gray, None)

            # Stabilization
            stabilized_frame = stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf)

            # Run detection model on stabilized frame
            detection_result = detection_model.predict(stabilized_frame)
            current_time = time.time()
            should_print = current_time - last_print_time >= print_interval
            
            if detection_result._inference_results:
                # Update tracked objects with current detections
                tracked_objects = update_tracked_objects(detection_result._inference_results)
                
                if should_print:
                    last_print_time = current_time
                    # Run depth model on stabilized frame
                    depth_result = depth_model.predict(stabilized_frame)
                    
                    for track_id, tracked_obj in tracked_objects.items():
                        bbox = tracked_obj['bbox']
                        label = tracked_obj['label']
                        is_new_object = tracked_obj.get('is_new', False)
                        
                        # Correct scaling from original frame (640x480) to 224x224
                        x_min = int(bbox[0] * xscale)
                        y_min = int(bbox[1] * yscale)
                        x_max = int(bbox[2] * xscale)
                        y_max = int(bbox[3] * yscale)
                        
                        # Ensure coordinates are within bounds
                        x_min = max(0, min(x_min, 223))
                        y_min = max(0, min(y_min, 223))
                        x_max = max(0, min(x_max, 223))
                        y_max = max(0, min(y_max, 223))
                        
                        if x_max > x_min and y_max > y_min:
                            # Get the depth map
                            raw_data = depth_result._inference_results[0]['data']
                            # Reshape to 2D (224, 224)
                            raw_data = raw_data.reshape((224, 224))
                            # Get center coordinates of the bounding box
                            center_x = (x_min + x_max) // 2
                            center_y = (y_min + y_max) // 2
                            # Get the depth value at the center of the bounding box
                            center_depth = raw_data[center_y, center_x]
                            
                            # Update depth history and get averaged depth
                            averaged_depth = update_depth_history(track_id, center_depth)
                            
                            # Only print if it's a new object or depth changed significantly
                            if should_print_depth(track_id, averaged_depth, is_new_object):
                                status = "NEW" if is_new_object else "UPDATED"
                                print(f"Track ID {track_id} - {label} ({status}): depth {averaged_depth:.2f}")
                        
                        # Mark object as no longer new after processing
                        tracked_obj['is_new'] = False
            
            output_display.show(detection_result)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            prev_gray = gray
            prev_kp = kp
            prev_des = des
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()


