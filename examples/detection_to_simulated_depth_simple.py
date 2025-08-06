import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import collections
import time

class DepthCalculator:
    def __init__(self):
        self.frame_depth_base = 150.0  # Base depth value
        self.frame_count = 0
        
        # Simplified debouncing - just stable frames
        self.stable_frames_required = 3  # Frames needed for stable detection
        self.detection_history = collections.defaultdict(list)  # Track detection history
        
        # Object tracking for IDs
        self.tracked_objects = {}  # Track objects across frames
        self.next_track_id = 1
        self.iou_threshold = 0.3
    
    def calculate_simulated_depth(self, bbox, frame_number):
        """Calculate simulated depth based on bounding box size and position"""
        # Extract bbox coordinates (DeGirum format: [x_min, y_min, x_max, y_max])
        x_min, y_min, x_max, y_max = bbox
        
        # Calculate bbox dimensions
        width = x_max - x_min
        height = y_max - y_min
        bbox_area = width * height
        
        # Normalize area (assuming max area is 0.5 of frame for 640x480 input)
        frame_area = 640 * 480
        normalized_area = min(bbox_area / frame_area, 0.5) / 0.5
        
        # Closer objects (larger area) have smaller depth values
        base_depth = self.frame_depth_base * (1.0 - normalized_area * 0.5)
        
        # Add some variation based on y position (lower in frame = closer)
        # Normalize y_center to [0, 1] where 1 is bottom of frame
        y_center = (y_min + y_max) / 2
        y_factor = y_center / 480.0  # Assuming 480p height
        depth_variation = base_depth * 0.3 * y_factor
        
        # Add small frame-based variation to simulate real depth changes
        frame_variation = 5.0 * np.sin(frame_number * 0.1)
        
        simulated_depth = base_depth - depth_variation + frame_variation
        return max(10.0, simulated_depth)  # Ensure minimum depth of 10
    
    def calculate_iou(self, box1, box2):
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Calculate intersection coordinates
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        # Check if there's any intersection
        if inter_x_min >= inter_x_max or inter_y_min >= inter_y_max:
            return 0.0
        
        # Calculate intersection area
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # Calculate union area
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def update_tracked_objects(self, detections):
        """Update tracked objects with new detections."""
        new_tracked_objects = {}
        used_track_ids = set()
        
        for detection in detections:
            bbox = detection['bbox']
            label = detection['label']
            confidence = detection['score']
            
            best_match_id = None
            best_iou = 0
            
            # Find best matching tracked object
            for track_id, tracked_obj in self.tracked_objects.items():
                if tracked_obj['label'] == label:  # Only match same label
                    iou = self.calculate_iou(bbox, tracked_obj['bbox'])
                    if iou > best_iou and iou > self.iou_threshold:
                        best_iou = iou
                        best_match_id = track_id
            
            # Assign track ID
            if best_match_id is not None and best_match_id not in used_track_ids:
                track_id = best_match_id
                used_track_ids.add(track_id)
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
            
            new_tracked_objects[track_id] = {
                'bbox': bbox,
                'confidence': confidence,
                'label': label,
                'detection': detection
            }
        
        self.tracked_objects = new_tracked_objects
        return new_tracked_objects
    
    def is_detection_stable(self, bbox, label, confidence):
        """Check if detection is stable across multiple frames"""
        # Create detection key based on label and approximate position
        detection_key = f"{label}_{int(bbox[0]/50)}_{int(bbox[1]/50)}"  # Grid-based key
        
        # Add current detection to history
        self.detection_history[detection_key].append({
            'bbox': bbox,
            'confidence': confidence,
            'frame': self.frame_count
        })
        
        # Keep only recent frames (just what we need for stability check)
        if len(self.detection_history[detection_key]) > self.stable_frames_required:
            self.detection_history[detection_key].pop(0)
        
        # Check if we have enough consecutive stable detections
        recent_detections = self.detection_history[detection_key]
        
        # Need at least the required number of frames
        if len(recent_detections) >= self.stable_frames_required:
            # Check if frames are consecutive (no gaps)
            frame_numbers = [d['frame'] for d in recent_detections]
            expected_frames = list(range(frame_numbers[0], frame_numbers[0] + len(frame_numbers)))
            
            if frame_numbers == expected_frames:
                return True
        
        return False
    
    def filter_detections(self, detections):
        """Filter and debounce detections"""
        filtered_detections = []
        
        for detection in detections:
            bbox = detection['bbox']
            label = detection['label']
            confidence = detection['score']
            
            # Apply debouncing logic
            if self.is_detection_stable(bbox, label, confidence):
                filtered_detections.append(detection)
        
        return filtered_detections
    
    def process_frame_detections(self, detections):
        """Process detections and return tracking info with formatted output"""
        # Filter stable detections
        filtered_detections = self.filter_detections(detections)
        
        if not filtered_detections:
            return None, 0, ""
        
        # Update object tracking
        tracked_objects = self.update_tracked_objects(filtered_detections)
        
        # Generate output string like the original format
        detection_count = 0
        string_to_print = f"Frame count: {self.frame_count}\n"
        
        for track_id, tracked_obj in tracked_objects.items():
            bbox = tracked_obj['bbox']
            label = tracked_obj['label']
            confidence = tracked_obj['confidence']
            
            # Calculate depth for this detection
            depth = self.calculate_simulated_depth(bbox, self.frame_count)
            
            string_to_print += (f"Detection: ID: {track_id} Label: {label} "
                              f"Confidence: {confidence:.2f} Depth: {depth:.2f}\n")
            detection_count += 1
        
        # Calculate simulated overall frame depth
        overall_depth = self.frame_depth_base + 10.0 * np.sin(self.frame_count * 0.05)
        
        string_to_print += f"Total detections: {detection_count}\n"
        string_to_print += f"Overall frame depth: {overall_depth:.2f}\n"
        
        return tracked_objects, detection_count, string_to_print

# Initialize components
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
camera.start()

model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

depth_calculator = DepthCalculator()

with degirum_tools.Display("Object Detection with Depth") as output_display:
    while True:
        frame = camera.capture_array("main")
        result = model.predict(frame)
        
        # Increment frame count
        depth_calculator.frame_count += 1
        
        # Process detections and calculate depth
        if result._inference_results:
            # Process detections with tracking and formatting
            tracked_objects, detection_count, output_string = depth_calculator.process_frame_detections(result._inference_results)
            
            if tracked_objects:
                # Print the formatted output (like original Hailo example)
                print(output_string)
                
                # Create annotated frame
                annotated_frame = frame.copy()
                
                for track_id, tracked_obj in tracked_objects.items():
                    bbox = tracked_obj['bbox']
                    label = tracked_obj['label']
                    confidence = tracked_obj['confidence']
                    
                    # Calculate depth for display
                    depth = depth_calculator.calculate_simulated_depth(bbox, depth_calculator.frame_count)
                    
                    # Draw bounding box (green for stable detections)
                    x_min, y_min, x_max, y_max = [int(coord) for coord in bbox]
                    cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                    
                    # Add label with ID and depth information
                    label_text = f"ID:{track_id} {label} D:{depth:.1f}"
                    cv2.putText(annotated_frame, label_text, (x_min, y_min-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Add frame info overlay
                cv2.putText(annotated_frame, f"Frame: {depth_calculator.frame_count}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(annotated_frame, f"Detections: {detection_count}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                output_display.show(annotated_frame)
            else:
                output_display.show(frame)
        else:
            output_display.show(frame)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.stop()

        

