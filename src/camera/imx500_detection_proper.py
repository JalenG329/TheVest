#!/usr/bin/env python3
"""
Proper IMX500 detection parser based on actual output format.
"""

from picamera2 import Picamera2
from picamera2.devices import IMX500
import numpy as np
import cv2
import time

def load_class_names(labels_file):
    """Load class names from labels file."""
    with open(labels_file, 'r', encoding="utf-8") as f:
        return f.read().splitlines()

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
        
        print(f"Number of valid detections: {num_detections}")
        
        # Process only the valid detections
        for i in range(min(num_detections, len(bboxes))):
            confidence = float(scores[i])
            class_id = int(class_ids[i])
            
            if confidence >= threshold and 0 <= class_id < len(class_names):
                # Get bounding box coordinates
                x1, y1, x2, y2 = bboxes[i]
                
                # Convert coordinates to integers
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                
                # Ensure coordinates are within image bounds
                x1 = max(0, min(x1, img_width))
                y1 = max(0, min(y1, img_height))
                x2 = max(0, min(x2, img_width))
                y2 = max(0, min(y2, img_height))
                
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

def draw_detections(image, detections):
    """Draw bounding boxes and labels on image."""
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        class_name = detection['class_name']
        confidence = detection['confidence']
        
        # Draw bounding box
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label with background
        label = f"{class_name}: {confidence:.2f}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        cv2.rectangle(image, (x1, y1 - label_size[1] - 10), 
                     (x1 + label_size[0], y1), (0, 255, 0), -1)
        cv2.putText(image, label, (x1, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    
    return image

def main():
    # Load class names
    class_names = load_class_names("/home/rohan/degirum_wearable_device/coco.txt")
    print(f"Loaded {len(class_names)} class names")
    
    # Initialize IMX500 and camera
    imx500 = IMX500("/home/rohan/degirum_wearable_device/sony camera/imx500_network_yolo11n_pp.rpk")
    camera = Picamera2()
    config = camera.create_video_configuration()
    camera.start(config)
    
    try:
        frame_count = 0
        last_valid_detections = []
        frames_without_output = 0
        
        while True:
            frame_count += 1
            
            # Capture frame and metadata
            metadata = camera.capture_metadata()
            data = camera.capture_array()
            img_height, img_width = data.shape[:2]
            
            # Get network outputs
            network_outputs = imx500.get_outputs(metadata)
            
            # Check if network_outputs is valid
            if network_outputs is None:
                frames_without_output += 1
                if frame_count % 30 == 0:
                    print(f"Frame {frame_count}: No network outputs available (total: {frames_without_output})")
                
                # Use last valid detections for display if available
                detections = last_valid_detections if frames_without_output < 10 else []
            else:
                frames_without_output = 0
                # Extract detections
                detections = parse_imx500_detections(network_outputs, img_width, img_height, class_names, threshold=0.3)
                last_valid_detections = detections
            
            # Display results every 30 frames or when detections found
            if frame_count % 30 == 0 or detections:
                print(f"\n=== FRAME {frame_count} DETECTION RESULTS ===")
                print(f"Found {len(detections)} objects:")
                
                for i, detection in enumerate(detections):
                    print(f"  {i+1}. {detection['class_name']} "
                          f"(confidence: {detection['confidence']:.3f}) "
                          f"bbox: {detection['bbox']} "
                          f"size: {detection['size']}")
            
            # Draw detections on image
            try:
                if detections:
                    annotated_image = draw_detections(data.copy(), detections)
                    cv2.imshow('IMX500 Detection', annotated_image)
                else:
                    cv2.imshow('IMX500 Detection', data)
            except cv2.error as e:
                print(f"OpenCV error: {e}")
                # Continue without display
            
            # Break on 'q' key press
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            
            # Add frame rate control - process at most 10 FPS
            time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\nStopping detection...")
        
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
