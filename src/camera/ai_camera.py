from importlib import metadata
from picamera2 import Picamera2
from picamera2.devices import IMX500
import cv2
import numpy as np

def load_class_names(labels_file):
    """Load class names from labels file."""
    with open(labels_file, 'r', encoding="utf-8") as f:
        return f.read().splitlines()

def extract_detections(network_outputs, img_width, img_height, class_names, threshold=0.5):
    """
    Extract detections from IMX500 network outputs.
    
    IMX500 output format:
    - Output 0: (300, 4) - Bounding boxes in format [x1, y1, x2, y2]
    - Output 1: (300,) - Confidence scores
    - Output 2: (300,) - Class IDs
    - Output 3: (1,) - Number of valid detections
    
    Returns:
        List of detections, each containing:
        - class_name: string name of detected object
        - bbox: (x1, y1, x2, y2) bounding box coordinates
        - confidence: detection confidence score
    """
    detections = []
    
    if isinstance(network_outputs, (list, tuple)) and len(network_outputs) >= 4:
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
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                x1 = max(0, min(x1, img_width))
                y1 = max(0, min(y1, img_height))
                x2 = max(0, min(x2, img_width))
                y2 = max(0, min(y2, img_height))
                
                # Calculate center and size
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                width = x2 - x1
                height = y2 - y1
                
                detections.append({
                    'class_name': class_names[class_id],
                    'class_id': class_id,
                    'bbox': (x1, y1, x2, y2),
                    'confidence': confidence,
                    'center': (center_x, center_y),
                    'size': (width, height)
                })
    
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

# Load class names
class_names = load_class_names("/home/rohan/degirum_wearable_device/coco.txt")

# Initialize IMX500 and camera
imx500 = IMX500("/home/rohan/degirum_wearable_device/sony camera/imx500_network_yolo11n_pp.rpk")
camera = Picamera2()
config = camera.create_video_configuration()
camera.start(config)

try:
    while True:
        # Capture frame and metadata
        metadata = camera.capture_metadata()
        data = camera.capture_array()
        
        # Get network outputs from IMX500
        network_outputs = imx500.get_outputs(metadata)
        
        # Extract detections with proper parsing
        img_height, img_width = data.shape[:2]
        detections = extract_detections(network_outputs, img_width, img_height, class_names, threshold=0.3)
        
        # Print detection results
        if detections:
            print(f"\nFrame detections ({len(detections)} objects found):")
            for i, detection in enumerate(detections):
                print(f"  {i+1}. {detection['class_name']} "
                      f"(confidence: {detection['confidence']:.3f}) "
                      f"bbox: {detection['bbox']} "
                      f"center: ({detection['center'][0]:.1f}, {detection['center'][1]:.1f}) "
                      f"size: {detection['size']}")
        
        # Draw detections on image
        annotated_image = draw_detections(data.copy(), detections)
        
        # Display the image (optional)
        cv2.imshow('IMX500 Detection', annotated_image)
        
        # Break on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\nStopping detection...")

finally:
    camera.stop()
    cv2.destroyAllWindows()

