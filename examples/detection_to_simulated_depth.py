"""
DeGirum-based implementation of detection with simulated depth estimation.
This implementation mimics the Hailo GStreamer pipeline example but uses DeGirum framework
for person detection and simulates depth information.
"""

import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2
import numpy as np
import time
import collections

# -----------------------------------------------------------------------------------------------
# User-defined class to manage frame processing and simulated depth calculation
# -----------------------------------------------------------------------------------------------
class UserAppManager:
    def __init__(self):
        self.frame_count = 0
        self.current_track_ids = set()  # Keep track of visible objects
        self.frame_depth_base = 150.0  # Base depth value
        self.tracked_objects = {}  # Track objects across frames
        self.next_track_id = 1
        self.depth_history = {}  # Track depth history for each object
        
        # Tracking parameters
        self.iou_threshold = 0.3
        self.depth_history_size = 3
        
    def increment_frame_count(self):
        """Increment and return the frame count"""
        self.frame_count += 1
        return self.frame_count
    
    def get_frame_count(self):
        """Get current frame count"""
        return self.frame_count
    
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
        """Update tracked objects with new detections (simplified tracking)."""
        # Filter for person detections only
        person_detections = [det for det in detections if det['label'] == 'person']
        
        new_tracked_objects = {}
        used_track_ids = set()
        
        for detection in detections:
            bbox = detection['bbox']
            confidence = detection['score']
            
            best_match_id = None
            best_iou = 0
            
            # Find best matching tracked object
            for track_id, tracked_obj in self.tracked_objects.items():
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
                'label': detection['label'],  
                'is_new': track_id not in self.tracked_objects
            }
        
        self.tracked_objects = new_tracked_objects
        return new_tracked_objects
    
    def update_depth_history(self, track_id, depth_value):
        """Update depth history for an object and return averaged depth."""
        if track_id not in self.depth_history:
            self.depth_history[track_id] = collections.deque(maxlen=self.depth_history_size)
        
        self.depth_history[track_id].append(depth_value)
        return sum(self.depth_history[track_id]) / len(self.depth_history[track_id])

# -----------------------------------------------------------------------------------------------
# Main application processing function (replaces the GStreamer callback)
# -----------------------------------------------------------------------------------------------
def process_frame(frame, app_manager, detection_model, display_frame=True):
    """Process a single frame - equivalent to the app_callback function"""
    
    # Increment frame counter
    frame_count = app_manager.increment_frame_count()
    
    # Run detection inference
    detection_result = detection_model.predict(frame)
    
    # Parse the detections with depth information
    detection_count = 0
    current_frame_tracks = set()
    string_to_print = f"Frame count: {frame_count}\n"
    
    if detection_result._inference_results:
        # Update tracked objects with current detections
        tracked_objects = app_manager.update_tracked_objects(detection_result._inference_results)
        
        for track_id, tracked_obj in tracked_objects.items():
            bbox = tracked_obj['bbox']
            confidence = tracked_obj['confidence']
            label = tracked_obj['label']
            
            current_frame_tracks.add(track_id)
            
            # Calculate simulated depth for this detection
            detection_depth = app_manager.calculate_simulated_depth(bbox, frame_count)
            
            # Update depth history and get averaged depth
            averaged_depth = app_manager.update_depth_history(track_id, detection_depth)
            
            string_to_print += (f"Detection: ID: {track_id} Label: {label} "
                              f"Confidence: {confidence:.2f} Depth: {averaged_depth:.2f}\n")
            detection_count += 1
    
    # Calculate simulated overall frame depth
    overall_depth = app_manager.frame_depth_base + 10.0 * np.sin(frame_count * 0.05)
    
    string_to_print += f"Total detections: {detection_count}\n"
    string_to_print += f"Overall frame depth: {overall_depth:.2f}\n"
    
    # Update the set of currently tracked objects
    app_manager.current_track_ids = current_frame_tracks
    
    # Add visual overlays if displaying frame
    if display_frame and detection_result._inference_results:
        # Create a copy of the frame for annotation
        annotated_frame = frame.copy()
        
        # Display the detection count and depth information on the frame
        cv2.putText(annotated_frame, f"Detections: {detection_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Frame Depth: {overall_depth:.2f}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # Display individual detection info on frame
        y_offset = 90
        for track_id, tracked_obj in tracked_objects.items():
            bbox = tracked_obj['bbox']
            confidence = tracked_obj['confidence']
            
            # Draw bounding box
            x_min, y_min, x_max, y_max = [int(coord) for coord in bbox]
            cv2.rectangle(annotated_frame, (x_min, y_min), (x_max, y_max), (255, 0, 0), 1)
            
            # Calculate and display depth
            detection_depth = app_manager.calculate_simulated_depth(bbox, frame_count)
            averaged_depth = app_manager.update_depth_history(track_id, detection_depth)
            
            # Add text labels
            cv2.putText(annotated_frame, f"ID {track_id}: {averaged_depth:.2f}", 
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            cv2.putText(annotated_frame, f"ID:{track_id} D:{averaged_depth:.1f}", 
                       (x_min, y_min-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            y_offset += 25
        
        print(string_to_print)
        return annotated_frame
    else:
        print(string_to_print)
        return frame

# -----------------------------------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------------------------------
def main():
    """Main application - replaces the GStreamerDetectionApp functionality"""
    
    # Initialize camera
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    camera.start()
    
    # Load detection model
    model1 = dg.load_model(
        model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
        inference_host_address="@local",
        zoo_url="/home/rohan/degirum_wearable_device/models"
    )

    model2 = dg.load_model(
        model_name="indoor_env_best--640x640_quant_hailort_hailo8_1",
        inference_host_address="@local",
        zoo_url="/home/rohan/degirum_wearable_device/models"
    )

    # Combine models into a compound model
    detection_model = CombiningCompoundModel(model1, model2)
    
    # Create application manager (equivalent to user_app_callback_class)
    app_manager = UserAppManager()
    
    print("Starting DeGirum Detection with Simulated Depth Application")
    print("Press 'q' to quit")
    
    # Main processing loop
    with degirum_tools.Display("DeGirum Detection with Simulated Depth") as output_display:
        try:
            while True:
                # Capture frame
                frame = camera.capture_array("main")
                
                # Process frame (equivalent to app_callback)
                processed_frame = process_frame(frame, app_manager, detection_model, display_frame=True)
                
                # Display result
                output_display.show(processed_frame)
                
                
                    
        except KeyboardInterrupt:
            print("\nApplication stopped by user")
        finally:
            camera.stop()

if __name__ == "__main__":
    main()