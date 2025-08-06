#!/usr/bin/env python3
"""
Simple IMX500 detection script for debugging - no display required.
"""

from picamera2 import Picamera2
from picamera2.devices import IMX500
import numpy as np
import time

def load_class_names(labels_file):
    """Load class names from labels file."""
    with open(labels_file, 'r', encoding="utf-8") as f:
        return f.read().splitlines()

def parse_imx500_detections(network_outputs, img_width, img_height, class_names, threshold=0.5):
    """Parse IMX500 specific output format."""
    detections = []
    
    # Check if network_outputs is valid
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

def main():
    # Load class names
    class_names = load_class_names("/home/rohan/degirum_wearable_device/coco.txt")
    print(f"Loaded {len(class_names)} class names")
    
    # Initialize IMX500 and camera
    print("Initializing IMX500 and camera...")
    imx500 = IMX500("/home/rohan/degirum_wearable_device/sony camera/imx500_network_yolo11n_pp.rpk")
    camera = Picamera2()
    config = camera.create_video_configuration()
    camera.start(config)
    
    print("Starting detection loop...")
    
    try:
        frame_count = 0
        detection_count = 0
        total_detections = 0
        
        start_time = time.time()
        
        while frame_count < 100:  # Run for 100 frames
            frame_count += 1
            
            # Capture frame and metadata
            metadata = camera.capture_metadata()
            data = camera.capture_array()
            img_height, img_width = data.shape[:2]
            
            # Get network outputs
            network_outputs = imx500.get_outputs(metadata)
            
            if network_outputs is not None:
                # Extract detections
                detections = parse_imx500_detections(network_outputs, img_width, img_height, class_names, threshold=0.3)
                
                if detections:
                    detection_count += 1
                    total_detections += len(detections)
                    
                    print(f"\n=== FRAME {frame_count} ===")
                    print(f"Found {len(detections)} objects:")
                    
                    for i, detection in enumerate(detections):
                        print(f"  {i+1}. {detection['class_name']} "
                              f"(conf: {detection['confidence']:.3f}) "
                              f"bbox: {detection['bbox']}")
            else:
                if frame_count % 10 == 0:
                    print(f"Frame {frame_count}: No network outputs")
            
            # Small delay
            time.sleep(0.1)
        
        # Print summary
        elapsed = time.time() - start_time
        print(f"\n=== SUMMARY ===")
        print(f"Processed {frame_count} frames in {elapsed:.1f} seconds")
        print(f"Frames with detections: {detection_count}")
        print(f"Total objects detected: {total_detections}")
        print(f"Average FPS: {frame_count/elapsed:.1f}")
        
    except KeyboardInterrupt:
        print("\nStopping detection...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        camera.stop()
        print("Camera stopped.")

if __name__ == "__main__":
    main()
