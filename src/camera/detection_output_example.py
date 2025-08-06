#!/usr/bin/env python3
"""
Simple example showing what detection outputs look like from IMX500.
"""

from picamera2 import Picamera2
from picamera2.devices import IMX500
import numpy as np

def load_class_names(labels_file):
    """Load class names from labels file."""
    with open(labels_file, 'r', encoding="utf-8") as f:
        return f.read().splitlines()

def parse_detection_outputs(network_outputs):
    """
    Parse and display the raw network outputs to understand the format.
    """
    print("=== RAW NETWORK OUTPUTS ===")
    print(f"Type: {type(network_outputs)}")
    
    if isinstance(network_outputs, (list, tuple)):
        print(f"Length: {len(network_outputs)}")
        for i, output in enumerate(network_outputs):
            print(f"Output {i}:")
            print(f"  Type: {type(output)}")
            if hasattr(output, 'shape'):
                print(f"  Shape: {output.shape}")
                print(f"  Dtype: {output.dtype}")
                if output.size < 100:  # Only print small arrays
                    print(f"  Data: {output}")
                else:
                    print(f"  Data (sample): {output.flat[:10]}...")
    else:
        print(f"Shape: {network_outputs.shape if hasattr(network_outputs, 'shape') else 'No shape'}")
        if hasattr(network_outputs, 'dtype'):
            print(f"Dtype: {network_outputs.dtype}")

def extract_yolo_detections(network_outputs, img_width, img_height, class_names, threshold=0.5):
    """
    Extract YOLO-format detections.
    
    Expected format for YOLO11:
    - Output shape: [1, num_detections, 84] for COCO (80 classes + 4 coords)
    - Each detection: [x_center, y_center, width, height, class0_conf, class1_conf, ...]
    """
    detections = []
    
    if not isinstance(network_outputs, (list, tuple)):
        outputs = [network_outputs]
    else:
        outputs = network_outputs
    
    for output in outputs:
        if hasattr(output, 'shape') and len(output.shape) >= 2:
            # Remove batch dimension if present
            if len(output.shape) == 3 and output.shape[0] == 1:
                output = output[0]
            
            print(f"Processing output shape: {output.shape}")
            
            for detection in output:
                if len(detection) >= 84:  # YOLO11 format for COCO
                    x_center, y_center, width, height = detection[:4]
                    class_scores = detection[4:]
                    
                    # Find class with highest confidence
                    max_class_id = np.argmax(class_scores)
                    max_confidence = class_scores[max_class_id]
                    
                    if max_confidence >= threshold:
                        # Convert to pixel coordinates
                        x0 = int((x_center - width/2) * img_width)
                        y0 = int((y_center - height/2) * img_height)
                        x1 = int((x_center + width/2) * img_width)
                        y1 = int((y_center + height/2) * img_height)
                        
                        # Ensure coordinates are within image bounds
                        x0 = max(0, min(x0, img_width))
                        y0 = max(0, min(y0, img_height))
                        x1 = max(0, min(x1, img_width))
                        y1 = max(0, min(y1, img_height))
                        
                        if max_class_id < len(class_names):
                            detection_info = {
                                'class_name': class_names[max_class_id],
                                'class_id': max_class_id,
                                'confidence': float(max_confidence),
                                'bbox': (x0, y0, x1, y1),
                                'center': (float(x_center), float(y_center)),
                                'size': (float(width), float(height))
                            }
                            detections.append(detection_info)
    
    return detections

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
        print("\nCapturing single frame for analysis...")
        
        # Capture frame and metadata
        metadata = camera.capture_metadata()
        data = camera.capture_array()
        img_height, img_width = data.shape[:2]
        
        print(f"Image dimensions: {img_width}x{img_height}")
        
        # Get network outputs
        network_outputs = imx500.get_outputs(metadata)
        
        # Parse raw outputs
        parse_detection_outputs(network_outputs)
        
        # Extract detections
        detections = extract_yolo_detections(network_outputs, img_width, img_height, class_names)
        
        # Display results
        print(f"\n=== DETECTION RESULTS ===")
        print(f"Found {len(detections)} objects:")
        
        for i, detection in enumerate(detections):
            print(f"\nDetection {i+1}:")
            print(f"  Class: {detection['class_name']} (ID: {detection['class_id']})")
            print(f"  Confidence: {detection['confidence']:.3f}")
            print(f"  Bounding Box: {detection['bbox']}")
            print(f"  Center (normalized): ({detection['center'][0]:.3f}, {detection['center'][1]:.3f})")
            print(f"  Size (normalized): ({detection['size'][0]:.3f}, {detection['size'][1]:.3f})")
        
        if not detections:
            print("  No objects detected above threshold")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        camera.stop()

if __name__ == "__main__":
    main()
