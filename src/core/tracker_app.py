import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time

# Initialize Picamera2
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
camera.start()

# Load the detection model
model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

# Load the depth model
depth_model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

# Create object tracker with improved settings
tracker = degirum_tools.ObjectTracker(
    track_thresh=0.3,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=True
)

# Initialize frame stabilization
orb = cv2.ORB_create(2000)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
prev_gray = None
prev_kp = None
prev_des = None
min_matches = 200

# Depth processing variables
last_print_time = 0
print_interval = 0.2  # seconds
xscale = 224 / 640  # Width scaling for depth map
yscale = 224 / 480   # Height scaling for depth map

# Define navigation obstacles
WALKING_OBSTACLES = {'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck', 
                    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 
                    'bench', 'chair', 'potted plant', 'dining table', 'couch'}

def stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf, min_matches=200):
    """Stabilize frame using ORB features and affine transformation."""
    if prev_gray is not None and prev_des is not None and des is not None and len(prev_kp) > 0 and len(kp) > 0:
        matches = bf.match(prev_des, des)
        matches = sorted(matches, key=lambda x: x.distance)
        if len(matches) > min_matches:
            src_pts = np.float32([prev_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            m, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC)
            if m is not None:
                stabilized_frame = cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), 
                                                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
                return stabilized_frame
    return frame

def get_depth_string(depth_value):
    """Convert depth value to descriptive string."""
    if 0 < depth_value < 20:
        return "far"
    elif 20 <= depth_value < 40:
        return "close"
    elif 40 <= depth_value:
        return "near"
    else:
        return "unknown"

with degirum_tools.Display("Object Detection Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Extract ORB features for stabilization
        kp, des = orb.detectAndCompute(gray, None)
        
        # Stabilize frame
        stabilized_frame = stabilize_frame(frame, gray, kp, des, prev_gray, prev_kp, prev_des, orb, bf, min_matches)
        
        # Run detection on stabilized frame
        result = model.predict(stabilized_frame)
        tracker.analyze(result)
        
        # Process depth for navigation obstacles
        current_time = time.time()
        should_print = current_time - last_print_time >= print_interval
        
        if result._inference_results and should_print:
            last_print_time = current_time
            
            # Run depth model on stabilized frame
            depth_result = depth_model.predict(stabilized_frame)
            
            for detection in result._inference_results:
                label = detection['label']
                
                # Only process navigation-relevant obstacles
                if label in WALKING_OBSTACLES:
                    bbox = detection['bbox']
                    
                    # Scale bounding box coordinates to depth map size
                    x_min = int(bbox[0] * xscale)
                    y_min = int(bbox[1] * yscale)
                    x_max = int(bbox[2] * xscale)
                    y_max = int(bbox[3] * yscale)
                    
                    # Ensure coordinates are within bounds
                    x_min = max(0, min(x_min, 223))
                    y_min = max(0, min(y_min, 223))
                    x_max = max(0, min(x_max, 223))
                    y_max = max(0, min(y_max, 223))
                    
                    if x_max > x_min and y_max > y_min:
                        # Get the depth map
                        raw_data = depth_result._inference_results[0]['data']
                        raw_data = raw_data.reshape((224, 224))
                        
                        # Get center coordinates of the bounding box
                        center_x = (x_min + x_max) // 2
                        center_y = (y_min + y_max) // 2
                        
                        # Get depth value at center of bounding box
                        center_depth = raw_data[center_y, center_x]
                        depth_str = get_depth_string(center_depth)
                        
                        print(f"Navigation Alert: {label} detected - {depth_str} (depth: {center_depth:.2f})")
        
        # Create overlay and display
        img = result.image_overlay
        img = tracker.annotate(result, img)
        output_display.show(img)
        
        # Update previous frame data for stabilization
        prev_gray = gray
        prev_kp = kp
        prev_des = des
        
        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()