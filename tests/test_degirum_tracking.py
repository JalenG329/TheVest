#!/usr/bin/env python3
"""
Test script to understand how DeGirum ObjectTracker works
and how to access track IDs from detection results.
"""

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import time

def test_tracking():
    """Test how DeGirum tracking works."""
    
    # Initialize camera
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    camera.start()
    
    # Load detection model
    model = dg.load_model(
        model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
        inference_host_address="@local",
        zoo_url="/home/rohan/degirum_wearable_device/models",
        overlay_show_labels=True,
        overlay_show_probabilities=True
    )
    
    # Create object tracker
    tracker = degirum_tools.ObjectTracker(
        track_thresh=0.3,
        anchor_point=degirum_tools.AnchorPoint.CENTER,
        show_overlay=True
    )
    
    print("Starting tracking test...")
    print("Look for track_id in detection results...")
    
    frame_count = 0
    max_frames = 20
    
    while frame_count < max_frames:
        frame = camera.capture_array("main")
        
        # Run detection
        result = model.predict(frame)
        
        # Apply tracking
        tracker.analyze(result)
        
        print(f"\n--- Frame {frame_count + 1} ---")
        print(f"Detection result type: {type(result)}")
        print(f"Has _inference_results: {hasattr(result, '_inference_results')}")
        
        if hasattr(result, '_inference_results') and result._inference_results:
            print(f"Number of detections: {len(result._inference_results)}")
            
            for i, detection in enumerate(result._inference_results):
                print(f"Detection {i}:")
                print(f"  Type: {type(detection)}")
                print(f"  Keys: {detection.keys() if hasattr(detection, 'keys') else 'Not a dict'}")
                
                if hasattr(detection, 'keys'):
                    for key in detection.keys():
                        print(f"    {key}: {detection[key]}")
                
                # Look specifically for track_id variations
                possible_track_keys = ['track_id', 'trackId', 'id', 'object_id', 'tracking_id']
                for key in possible_track_keys:
                    if key in detection:
                        print(f"  FOUND TRACK KEY '{key}': {detection[key]}")
        else:
            print("No detections found")
        
        frame_count += 1
        time.sleep(1)  # Wait a bit between frames
    
    camera.stop()
    print("Test completed.")

if __name__ == "__main__":
    test_tracking()
