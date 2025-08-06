#!/usr/bin/env python3
"""
Simple test script to identify the correct DeGirum track ID key
without requiring hardware components.
"""

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time

def test_track_id_key():
    """Test to identify the correct track ID key used by DeGirum ObjectTracker."""
    
    print("Initializing camera and models...")
    
    # Initialize camera
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"}))
    picam2.start()
    
    # Load a simple detection model
    detection_model = dg.load_model(
        "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1", 
        "@local",
        "/home/rohan/degirum_wearable_device/models",
        overlay_show_labels=True,
        overlay_show_probabilities=True
    )
    
    # Initialize object tracker
    tracker = degirum_tools.ObjectTracker(
        track_thresh=0.3,
        anchor_point=degirum_tools.AnchorPoint.CENTER,
        show_overlay=True
    )
    
    print("Starting detection test...")
    
    for frame_num in range(10):  # Test 10 frames
        print(f"\n--- Frame {frame_num + 1} ---")
        
        frame = picam2.capture_array("main")
        
        # Run detection
        detection_result = detection_model.predict(frame)
        
        # Apply tracking
        tracker.analyze(detection_result)
        
        # Check what we get
        if hasattr(detection_result, '_inference_results') and detection_result._inference_results:
            print(f"Found {len(detection_result._inference_results)} detections")
            
            for i, item in enumerate(detection_result._inference_results):
                print(f"Detection {i}:")
                print(f"  Available keys: {list(item.keys())}")
                
                # Check for track ID specifically
                track_id_found = False
                for key in item.keys():
                    if 'track' in key.lower() or 'id' in key.lower():
                        print(f"  Potential track key '{key}': {item[key]}")
                        track_id_found = True
                
                if not track_id_found:
                    print("  No obvious track ID keys found")
                
                # Limit output for readability
                if i >= 2:  # Only show first 3 detections
                    break
        else:
            print("No detections found")
        
        time.sleep(0.5)  # Small delay between frames
    
    picam2.stop()
    print("\nTest completed!")

if __name__ == "__main__":
    test_track_id_key()
