from picamera2 import Picamera2, Preview, MappedArray
from picamera2.devices import IMX500
from picamera2.devices import Hailo

import numpy as np
import time
import cv2

# Haptic feedback imports
import board
import busio
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
from threading import Thread

# Initialize I2C and haptic driver (uncomment to enable haptic feedback)
# I2C = busio.I2C(board.SCL, board.SDA)
# DRV = DRV2605(I2C)
HAPTIC_ENABLED = False  # Set to True to enable haptic feedback

# Configuration
DEPTH_HISTORY_SIZE = 3
DEPTH_CHANGE_THRESHOLD = 15
TARGET_OBJECTS = ["cell phone", "remote", "person", "bottle"]  # Objects to track and vibrate for
SCALE = (320/1280, 256/720)  # (x_scale, y_scale) for depth model input size

# Global state
tracked_objects = {}
next_track_id = 1
last_print_time = 0
depth_history = {}
depth_debug_printed = False  # Flag to print depth model output format once

def load_class_names(labels_file):
    """Load class names from labels file."""
    with open(labels_file, 'r', encoding="utf-8") as f:
        return f.read().splitlines()

def vibrate_motor(depth_value, min_depth=18.91, max_depth=79.79, min_v=0, max_v=127):
    """Vibrate motor based on depth value."""
    if not HAPTIC_ENABLED:
        return
        
    try:
        global DRV
        DRV.mode = MODE_REALTIME

        # Map depth value to a range suitable for vibration intensity
        def map_depth_to_vibrator(depth, min_d, max_d, min_v, max_v):
            if max_d == min_d:
                return min_v
            return int(min_v + (depth - min_d) * (max_v - min_v) / (max_d - min_d))

        mapped_value = map_depth_to_vibrator(depth_value, min_depth, max_depth, min_v, max_v)
        mapped_value = max(min_v, min(max_v, mapped_value))  # Clamp to valid range
        DRV.realtime_value = mapped_value
    except (NameError, AttributeError):
        print("Haptic feedback not available - DRV not initialized")
    except Exception as e:
        print(f"Haptic feedback error: {e}")

def parse_imx500_detections(network_outputs, img_width, img_height, class_names, threshold=0.5):
    """
    Parse IMX500 specific output format.
    
    Based on the output analysis:
    - Output 0: (300, 4) - Bounding boxes in format [x1, y1, x2, y2]
    - Output 1: (300,) - Confidence scores
    - Output 2: (300,) - Class IDs
    - Output 3: (1,) - Number of valid detections
    """
    detections = []
    
    # Check if network_outputs is valid and has expected structure
    if network_outputs is None:
        return detections
    
    if not isinstance(network_outputs, (list, tuple)) or len(network_outputs) < 4:
        return detections
    
    try:
        bboxes = network_outputs[0]      # Shape: (300, 4) - [x1, y1, x2, y2]
        scores = network_outputs[1]      # Shape: (300,) - confidence scores
        class_ids = network_outputs[2]   # Shape: (300,) - class IDs
        num_detections = int(network_outputs[3][0]) if len(network_outputs[3]) > 0 else 0
        
        # Process only the valid detections
        for i in range(min(num_detections, len(bboxes))):
            confidence = float(scores[i])
            class_id = int(class_ids[i])
            
            if confidence >= threshold and 0 <= class_id < len(class_names):
                # Get bounding box coordinates
                x1, y1, x2, y2 = bboxes[i]
                
                # Convert coordinates to integers and ensure they're within bounds
                x1 = max(0, min(int(x1), img_width))
                y1 = max(0, min(int(y1), img_height))
                x2 = max(0, min(int(x2), img_width))
                y2 = max(0, min(int(y2), img_height))
                
                # Calculate center and size
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1
                
                detection_info = {
                    'class_name': class_names[class_id],
                    'class_id': class_id,
                    'confidence': confidence,
                    'bbox': (x1, y1, x2, y2),
                    'center': (center_x, center_y),
                    'size': (width, height)
                }
                detections.append(detection_info)
    
    except (IndexError, ValueError, TypeError) as e:
        print(f"Error parsing network outputs: {e}")
        return []
    
    return detections

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
    global tracked_objects, next_track_id
    
    new_tracked_objects = {}
    used_track_ids = set()
    
    for detection in detections:
        bbox = detection['bbox']
        label = detection['class_name']
        confidence = detection['confidence']
        
        best_match_id = None
        best_iou = 0
        
        # Find best matching tracked object
        for track_id, tracked_obj in tracked_objects.items():
            if tracked_obj['label'] == label:
                iou = calculate_iou(bbox, tracked_obj['bbox'])
                if iou > best_iou and iou > 0.3:
                    best_iou = iou
                    best_match_id = track_id
        
        # Assign track ID
        if best_match_id and best_match_id not in used_track_ids:
            track_id = best_match_id
        else:
            track_id = next_track_id
            next_track_id += 1
        
        used_track_ids.add(track_id)
        
        new_tracked_objects[track_id] = {
            'bbox': bbox,
            'label': label,
            'confidence': confidence,
            'last_seen': time.time(),
            'is_new': track_id not in tracked_objects
        }
    
    # Clean up old objects (remove objects not seen for 2 seconds)
    current_time = time.time()
    tracked_objects = {k: v for k, v in new_tracked_objects.items() 
                      if current_time - v.get('last_seen', 0) < 2.0}
    
    return new_tracked_objects

def draw_detections_with_tracking(request):
    """Draw bounding boxes and labels on image with tracking info."""
    if tracked_objects:
        with MappedArray(request, "main") as m:
            for track_id, obj in tracked_objects.items():
                x1, y1, x2, y2 = obj['bbox']
                class_name = obj['label']
                confidence = obj['confidence']
                is_target = class_name in TARGET_OBJECTS
                
                # Choose color based on whether it's a target object
                color = (255, 0, 0) if is_target else (0, 255, 0)  # Red for targets, green for others
                
                # Draw bounding box
                cv2.rectangle(m.array, (x1, y1), (x2, y2), color, 2)
                
                # Draw label with background including depth info
                depth_info = ""
                if 'depth' in obj:
                    depth_method = obj.get('depth_method', 'unk')
                    depth_info = f" D:{obj['depth']:.2f}[{depth_method}]"
                
                label = f"ID:{track_id} {class_name}: {confidence:.2f}{depth_info}"
                if is_target:
                    label += " [TARGET]"
                
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                cv2.rectangle(m.array, (x1, y1 - label_size[1] - 10), 
                             (x1 + label_size[0], y1), color, -1)
                cv2.putText(m.array, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

def estimate_depth_from_bbox_size(bbox, baseline_size=50):
    """
    Estimate relative depth based on bounding box size.
    Larger objects are assumed to be closer.
    """
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    area = width * height
    
    # Simple inverse relationship: smaller area = further away
    # This is a rough approximation
    if area > 0:
        estimated_depth = baseline_size / (area ** 0.5) * 100
        return max(10, min(100, estimated_depth))  # Clamp between 10-100
    return 50  # Default depth

def get_depth_from_hailo(hailo_depth, frame, bbox):
    """
    Get depth estimation from Hailo depth model for a specific bounding box.
    """
    global depth_debug_printed
    
    try:
        # Resize frame to depth model input size (320x256)
        depth_input = cv2.resize(frame, (320, 256))
        
        # Run depth inference
        depth_results = hailo_depth.run(depth_input)
        
        # One-time debug print to understand output format
        if not depth_debug_printed:
            print(f"DEBUG: Depth results type: {type(depth_results)}")
            if depth_results is not None:
                if isinstance(depth_results, (list, tuple)):
                    print(f"DEBUG: Depth results length: {len(depth_results)}")
                    for i, result in enumerate(depth_results):
                        print(f"DEBUG: Result {i} type: {type(result)}, shape: {getattr(result, 'shape', 'no shape')}")
                elif isinstance(depth_results, np.ndarray):
                    print(f"DEBUG: Depth results shape: {depth_results.shape}")
            depth_debug_printed = True
        
        # Extract depth map (check if results exist and have content)
        if depth_results is not None and isinstance(depth_results, (list, tuple)) and len(depth_results) > 0:
            depth_map = depth_results[0]
            
            # Ensure depth_map is a numpy array with the expected shape
            if isinstance(depth_map, np.ndarray) and depth_map.size > 0:
                # Handle different possible output shapes
                if len(depth_map.shape) == 3:
                    # If 3D (e.g., 1x256x320 or 256x320x1), squeeze to 2D
                    depth_map = np.squeeze(depth_map)
                elif len(depth_map.shape) == 1:
                    # If 1D, reshape to expected 2D shape
                    depth_map = depth_map.reshape(256, 320)
                
                # Ensure we have a 2D depth map
                if len(depth_map.shape) == 2:
                    # Scale bbox coordinates to depth map size
                    x1, y1, x2, y2 = bbox
                    x_min = max(0, min(int(x1 * SCALE[0]), depth_map.shape[1] - 1))
                    y_min = max(0, min(int(y1 * SCALE[1]), depth_map.shape[0] - 1))
                    x_max = max(0, min(int(x2 * SCALE[0]), depth_map.shape[1] - 1))
                    y_max = max(0, min(int(y2 * SCALE[1]), depth_map.shape[0] - 1))
                    
                    # Ensure valid region
                    if x_max > x_min and y_max > y_min:
                        roi_depth = depth_map[y_min:y_max, x_min:x_max]
                        if roi_depth.size > 0:
                            average_depth = np.mean(roi_depth)
                            center_depth = depth_map[(y_min + y_max) // 2, (x_min + x_max) // 2]
                            
                            return float(average_depth), float(center_depth)
        elif depth_results is not None and isinstance(depth_results, np.ndarray):
            # Handle case where depth_results is directly a numpy array
            depth_map = depth_results
            
            if depth_map.size > 0:
                # Handle different possible output shapes
                if len(depth_map.shape) == 3:
                    depth_map = np.squeeze(depth_map)
                elif len(depth_map.shape) == 1:
                    depth_map = depth_map.reshape(256, 320)
                
                if len(depth_map.shape) == 2:
                    x1, y1, x2, y2 = bbox
                    x_min = max(0, min(int(x1 * SCALE[0]), depth_map.shape[1] - 1))
                    y_min = max(0, min(int(y1 * SCALE[1]), depth_map.shape[0] - 1))
                    x_max = max(0, min(int(x2 * SCALE[0]), depth_map.shape[1] - 1))
                    y_max = max(0, min(int(y2 * SCALE[1]), depth_map.shape[0] - 1))
                    
                    if x_max > x_min and y_max > y_min:
                        roi_depth = depth_map[y_min:y_max, x_min:x_max]
                        if roi_depth.size > 0:
                            average_depth = np.mean(roi_depth)
                            center_depth = depth_map[(y_min + y_max) // 2, (x_min + x_max) // 2]
                            
                            return float(average_depth), float(center_depth)
        
    except Exception as e:
        print(f"Error in depth estimation: {e}")
    
    # Fallback to bbox-based estimation
    return estimate_depth_from_bbox_size(bbox), estimate_depth_from_bbox_size(bbox)

def update_depth_history(track_id, depth_value):
    """Update depth history for smoothing depth values."""
    global depth_history
    
    if track_id not in depth_history:
        depth_history[track_id] = []
    
    depth_history[track_id].append(depth_value)
    
    # Keep only recent depth values
    if len(depth_history[track_id]) > DEPTH_HISTORY_SIZE:
        depth_history[track_id] = depth_history[track_id][-DEPTH_HISTORY_SIZE:]
    
    # Return smoothed depth value
    return np.mean(depth_history[track_id])

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

def main():
    global last_print_time, tracked_objects
    
    # Load class names
    class_names = load_class_names("/home/rohan/degirum_wearable_device/coco.txt")
    print(f"Loaded {len(class_names)} class names")
    print(f"Target objects for haptic feedback: {TARGET_OBJECTS}")
    
    # Initialize IMX500 for object detection
    imx500 = IMX500("/home/rohan/degirum_wearable_device/sony camera/imx500_network_yolo11n_pp.rpk")
    
    # Initialize Hailo for depth estimation
    try:
        hailo_depth = Hailo("/home/rohan/degirum_wearable_device/sony camera/scdepthv3.hef")
        depth_model_available = True
        print("Hailo depth model (scdepthv3) loaded successfully")
    except Exception as e:
        print(f"Warning: Could not load Hailo depth model: {e}")
        print("Falling back to bbox-based depth estimation")
        hailo_depth = None
        depth_model_available = False
    
    # Initialize camera
    camera = Picamera2()
    
    # Configure camera for both detection and depth processing
    main_config = {'size': (1280, 720), 'format': 'RGB888'}
    # Add low-res stream for depth processing if needed
    lores_config = {'size': (320, 256), 'format': 'RGB888'}
    config = camera.create_video_configuration(main=main_config, lores=lores_config)
    camera.configure(config)
    
    # Start camera without preview to avoid Qt issues
    camera.start()
    
    # Initialize frame stabilization
    orb = cv2.ORB_create(2000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    prev_gray = prev_kp = prev_des = None
    
    # Optional: Set up preview only if display is available
    try:
        camera.start_preview(Preview.QTGL, x=0, y=0, width=1280, height=720)
        camera.pre_callback = draw_detections_with_tracking
        preview_enabled = True
        print("Preview window enabled")
    except Exception as e:
        print(f"Preview disabled due to display issues: {e}")
        preview_enabled = False
    
    try:
        frame_count = 0
        last_valid_detections = []
        frames_without_output = 0
        
        print("Starting detection with haptic feedback...")
        if preview_enabled:
            print("Press 'q' in the preview window to quit")
        else:
            print("Running in headless mode - Press Ctrl+C to quit")
        
        while True:
            frame_count += 1
            
            # Capture frame and metadata
            metadata = camera.capture_metadata()
            data = camera.capture_array("main")
            img_height, img_width = data.shape[:2]
            
            # Apply frame stabilization
            gray = cv2.cvtColor(data, cv2.COLOR_RGB2GRAY)
            kp, des = orb.detectAndCompute(gray, None)
            stabilized_frame = stabilize_frame(data, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf)
            
            # Get network outputs from IMX500
            network_outputs = imx500.get_outputs(metadata)
            
            # Check if network_outputs is valid
            if network_outputs is None:
                frames_without_output += 1
                if frame_count % 60 == 0:
                    print(f"Frame {frame_count}: No network outputs available (total: {frames_without_output})")
                
                # Use last valid detections for tracking continuity
                detections = last_valid_detections if frames_without_output < 30 else []
            else:
                frames_without_output = 0
                # Extract detections
                detections = parse_imx500_detections(network_outputs, img_width, img_height, class_names, threshold=0.3)
                last_valid_detections = detections
            
            # Update tracking
            tracked_objects = update_tracked_objects(detections)
            
            # Process haptic feedback for target objects
            target_detected = False
            closest_target_depth = float('inf')
            
            for track_id, obj in tracked_objects.items():
                if obj['label'] in TARGET_OBJECTS:
                    target_detected = True
                    
                    # Get depth estimation - use Hailo if available, otherwise bbox-based
                    if depth_model_available and hailo_depth is not None:
                        try:
                            average_depth, center_depth = get_depth_from_hailo(hailo_depth, stabilized_frame, obj['bbox'])
                            # Smooth the depth value using history
                            smoothed_depth = update_depth_history(track_id, average_depth)
                            obj['depth'] = smoothed_depth
                            obj['depth_method'] = 'hailo'
                        except Exception as e:
                            print(f"Hailo depth estimation failed: {e}")
                            estimated_depth = estimate_depth_from_bbox_size(obj['bbox'])
                            obj['depth'] = estimated_depth
                            obj['depth_method'] = 'bbox'
                    else:
                        # Fallback to bbox-based estimation
                        estimated_depth = estimate_depth_from_bbox_size(obj['bbox'])
                        obj['depth'] = estimated_depth
                        obj['depth_method'] = 'bbox'
                    
                    # Use the closest target for vibration
                    if obj['depth'] < closest_target_depth:
                        closest_target_depth = obj['depth']
            
            # Control haptic feedback
            if HAPTIC_ENABLED and target_detected and closest_target_depth != float('inf'):
                # Vibrate based on the closest target object
                # Map depth values appropriately based on estimation method
                if depth_model_available:
                    vibrate_motor(closest_target_depth, min_depth=0.1, max_depth=10.0)  # Hailo depth values
                else:
                    vibrate_motor(closest_target_depth, min_depth=10, max_depth=100)    # Bbox depth values
            elif HAPTIC_ENABLED:
                # No target objects detected, turn off vibration
                try:
                    global DRV
                    DRV.realtime_value = 0
                except (NameError, AttributeError):
                    pass
            
            # Update stabilization variables
            prev_gray, prev_kp, prev_des = gray, kp, des
            
            # Display results every 60 frames
            current_time = time.time()
            if current_time - last_print_time >= 2.0:  # Print every 2 seconds
                last_print_time = current_time
                print(f"\n=== FRAME {frame_count} STATUS ===")
                print(f"Total objects tracked: {len(tracked_objects)}")
                print(f"Depth model: {'Hailo (scdepthv3)' if depth_model_available else 'BBox estimation'}")
                
                target_objects_found = [obj for obj in tracked_objects.values() if obj['label'] in TARGET_OBJECTS]
                print(f"Target objects detected: {len(target_objects_found)}")
                
                for track_id, obj in tracked_objects.items():
                    if obj['label'] in TARGET_OBJECTS:
                        depth = obj.get('depth', 'N/A')
                        depth_method = obj.get('depth_method', 'unknown')
                        print(f"  ID:{track_id} {obj['label']} (conf: {obj['confidence']:.3f}, "
                              f"depth: {depth:.3f} [{depth_method}])")
                
                if target_detected:
                    print(f"Haptic feedback active (closest depth: {closest_target_depth:.3f})")
                else:
                    print("Haptic feedback off")
            
            # Optional: Save detection images for debugging (uncomment if needed)
            # if target_detected and frame_count % 30 == 0:
            #     annotated_frame = data.copy()
            #     for track_id, obj in tracked_objects.items():
            #         if obj['label'] in TARGET_OBJECTS:
            #             x1, y1, x2, y2 = obj['bbox']
            #             cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            #             cv2.putText(annotated_frame, f"ID:{track_id} {obj['label']}", 
            #                        (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            #     cv2.imwrite(f"/tmp/detection_{frame_count}.jpg", cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
            
            # Add small delay to prevent overwhelming the system
            time.sleep(0.03)  # ~30 FPS processing
                
    except KeyboardInterrupt:
        print("\nStopping detection...")
        
    finally:
        # Clean shutdown
        # if HAPTIC_ENABLED:
        #     try:
        #         global DRV
        #         DRV.realtime_value = 0  # Turn off vibration
        #     except (NameError, AttributeError):
        #         pass
        if preview_enabled:
            camera.stop_preview()
        camera.stop()
        
        # Close Hailo depth model
        if depth_model_available and hailo_depth is not None:
            try:
                hailo_depth.close()
            except:
                pass
        
        print("Camera stopped, models closed, and haptic feedback disabled.")

if __name__ == "__main__":
    main()
