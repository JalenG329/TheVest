import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import time

# Initialize Picamera2
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (1920, 1080)}))
camera.start()

model = dg.load_model(
    model_name="indoor_env_last--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/haptic feedback vest final/models",  # Fixed path
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

with degirum_tools.Display("Object Detection Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        results = model.predict(frame)
        
        # Print out detection results
        print("\n--- Detections in current frame ---")

        # Access detections from the results attribute
        detections = results.results if hasattr(results, 'results') else []
        
        # Debug: Print total number of detections before filtering
        print(f"Total detections found: {len(detections)}")
        
        detected_count = 0
        for detection in detections:
            # Since detection is a dict, print its contents
            print(f"Detection dictionary: {detection}")
            
            # Access dictionary keys instead of attributes
            label = "Unknown"
            confidence = 0.0
            
            # Try to get label from dict keys
            if 'label' in detection:
                label = detection['label']
            elif 'class_name' in detection:
                label = detection['class_name']
            elif 'category_id' in detection:
                label = f"Class {detection['category_id']}"
            elif 'class_id' in detection:
                label = f"Class {detection['class_id']}"
            
            # Try to get confidence/score from dict keys
            if 'score' in detection:
                confidence = detection['score'] * 100
            elif 'confidence' in detection:
                confidence = detection['confidence'] * 100
            elif 'prob' in detection:
                confidence = detection['prob'] * 100
            
            print(f"Object detected: {label} ({confidence:.1f}%)")
            
            # Try to get bounding box from dict keys
            if 'bbox' in detection:
                bbox = detection['bbox']
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    print(f"  Position: [{int(x1)},{int(y1)}]-[{int(x2)},{int(y2)}]")
            elif 'box' in detection:
                print(f"  Box: {detection['box']}")
            elif 'coordinates' in detection:
                print(f"  Coordinates: {detection['coordinates']}")
            
            detected_count += 1
        
        print(f"Total objects detected this frame: {detected_count}")
        
        if len(detections) == 0:
            print("No objects detected in this frame")
            # Debug model info
            print("Model info:")
            if hasattr(results, 'info'):
                print(f"  Model info: {results.info}")
            if hasattr(results, 'timing'):
                print(f"  Timing: {results.timing}")
        
        # Add frame counter to reduce spam
        time.sleep(0.5)  # Add a small delay
        
        # output_display.show(results)


