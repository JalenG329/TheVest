from unittest import result
import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2
import numpy as np

import board
import busio

import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
import adafruit_drv2605

import time
from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

# Camera and model resolution constants
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_RESOLUTION = (CAMERA_WIDTH, CAMERA_HEIGHT)
DEPTH_MODEL_SIZE = 224
DEPTH_MODEL_RESOLUTION = (DEPTH_MODEL_SIZE, DEPTH_MODEL_SIZE)

SCALE = (DEPTH_MODEL_SIZE/CAMERA_WIDTH, DEPTH_MODEL_SIZE/CAMERA_HEIGHT)  # (x_scale, y_scale)
DEPTH_HISTORY_SIZE = 3
DEPTH_CHANGE_THRESHOLD = 15

# Denoising parameters
GAUSSIAN_KERNEL_SIZE = 5
GAUSSIAN_SIGMA = 1.5
TEMPORAL_SMOOTHING_ALPHA = 0.3  # Lower values = more smoothing

drv1 = DRV2605(mux[1])  # Channel 1
drv2 = DRV2605(mux[3])  # Channel 3
drv3 = DRV2605(mux[6])  # Channel 6
drv4 = DRV2605(mux[5])  # Channel 5
drv5 = DRV2605(mux[4])  # Channel 4
drv6 = DRV2605(mux[7])  # Channel 7
drv7 = DRV2605(mux[2])  # Channel 2
drv8 = DRV2605(mux[0])  # Channel 0

drvs = [drv2, drv3, drv4, drv5, drv6, drv7, drv8]

# Global variables for temporal smoothing
previous_depth_map = None
previous_avg_depths = None

# Object detection cooldown and tracking
last_vibration_times = {
    'person': 0,
    'stairs': 0,
    'exit': 0,
    'door': 0
}
# Track IDs we've already seen for each object type
seen_track_ids = {
    'person': set(),
    'stairs': set(),
    'exit': set(),
    'door': set()
}
COOLDOWN_TIME = 1.0  # 1 second cooldown

# Effect mapping for different objects
OBJECT_EFFECTS = {
    'person': 13,
    'stairs': 14,
    'exit': 15,
    'door': 16
}

DELAY = .1  # Delay between intensity changes

def vibrate_motor(intensity, drv, delay=DELAY):
    drv.mode = MODE_REALTIME
    drv.realtime_value = intensity  # Set to desired intensity
    time.sleep(delay)  # Vibrate for specified delay
    drv.realtime_value = 0
    drv.mode = MODE_INTTRIG


def depth_map_to_vibrator(depth_value, min_depth=0, max_depth=5, min_v=0, max_v=127):
    """Map depth value to a range suitable for vibration intensity."""
    if max_depth == min_depth:
        return min_v
    return int(min_v + (depth_value - min_depth) * (max_v - min_v) / (max_depth - min_depth))

def init_models():
    """Initialize and return depth model and object detection model."""
    depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1", "@local",
                               "/home/rohan/degirum_wearable_device/models")
    yolo11n = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1", "@local",
                                   "/home/rohan/haptic feedback vest final/models",
                                   overlay_show_labels=True,
                                   overlay_show_probabilities=True)
    etec = dg.load_model("indoor_env_best--640x640_quant_hailort_hailo8_2", "@local",
                             "/home/rohan/degirum_wearable_device/models",
                             overlay_show_labels=True,
                             overlay_show_probabilities=True)
    return depth_model, CombiningCompoundModel(yolo11n, etec)
def init_picamera():
    """Initialize and return Picamera2 instance."""
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"size": CAMERA_RESOLUTION, "format": "RGB888"}))
    picam2.start()
    return picam2

def depth_processing(depth_result):
    """Process depth result and return denoised depth map for vibration analysis."""
    raw_data = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    depth_map = (raw_data.astype(np.float32) - zero) * scale
    depth_map = depth_map.reshape(DEPTH_MODEL_RESOLUTION)
    
    # Apply Gaussian blur for spatial denoising
    depth_map_denoised = cv2.GaussianBlur(depth_map, (GAUSSIAN_KERNEL_SIZE, GAUSSIAN_KERNEL_SIZE), GAUSSIAN_SIGMA)
    
    return depth_map_denoised

def depth_for_display(depth_map_denoised):
    """Convert denoised depth map to displayable color format."""
    # Resize to camera resolution for display
    resized_depth_map = cv2.resize(depth_map_denoised, CAMERA_RESOLUTION, interpolation=cv2.INTER_LINEAR)

    # Normalize to 0-255 for visualization
    depth_map_normalized = cv2.normalize(resized_depth_map, None, 0, 255, cv2.NORM_MINMAX)
    depth_map_normalized = np.uint8(depth_map_normalized)

    depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)
    return depth_map_color

def depth_in_7_segments(depth_map):
    """Divide depth map into 7 segments horizontally and return average depth for each segment with temporal smoothing."""
    global previous_depth_map, previous_avg_depths
    
    # Apply temporal smoothing if we have a previous frame
    if previous_depth_map is not None:
        depth_map = TEMPORAL_SMOOTHING_ALPHA * depth_map + (1 - TEMPORAL_SMOOTHING_ALPHA) * previous_depth_map
    
    height, width = depth_map.shape
    segment_width = width // 7
    avg_depths = []

    for i in range(7):
        segment = depth_map[:, i * segment_width:(i + 1) * segment_width]
        avg_depth = np.mean(segment)
        avg_depths.append(avg_depth)

    # Apply temporal smoothing to average depths
    if previous_avg_depths is not None:
        smoothed_avg_depths = []
        for i in range(7):
            smoothed_depth = TEMPORAL_SMOOTHING_ALPHA * avg_depths[i] + (1 - TEMPORAL_SMOOTHING_ALPHA) * previous_avg_depths[i]
            smoothed_avg_depths.append(smoothed_depth)
        avg_depths = smoothed_avg_depths

    print(f"Average depths for segments: {avg_depths}")

    # Store current values for next frame
    previous_depth_map = depth_map.copy()
    previous_avg_depths = avg_depths.copy()

    return avg_depths 

def trigger_object_detection_vibration(object_type, track_id):
    """Trigger vibration effect when specific object is detected with new track ID."""
    global last_vibration_times, seen_track_ids
    current_time = time.time()
    
    # Check if this is a new track ID for this object type
    if track_id not in seen_track_ids[object_type]:
        # Add to seen track IDs
        seen_track_ids[object_type].add(track_id)
        
        # Also respect cooldown to prevent rapid firing
        if current_time - last_vibration_times[object_type] >= COOLDOWN_TIME:
            effect_number = OBJECT_EFFECTS[object_type]
            drv1.sequence[0] = adafruit_drv2605.Effect(effect_number)
            drv1.play()
            last_vibration_times[object_type] = current_time
            print(f"NEW {object_type.capitalize()} detected! Track ID: {track_id}, Effect {effect_number} triggered at {current_time}")
        else:
            print(f"NEW {object_type.capitalize()} detected (Track ID: {track_id}) but in cooldown period")
    else:
        # This track ID has been seen before, no vibration
        print(f"Known {object_type} (Track ID: {track_id}) - no vibration")

def detect_objects(detection_result):
    """Check for multiple object types in detection results with track ID support."""
    detected_objects = []
    
    for item in detection_result._inference_results:
        label = item['label']
        
        # Get track ID directly - DeGirum ObjectTracker uses 'track_id' key
        track_id = item.get('track_id', None)
        
        # If no track ID is found, create a unique identifier based on bbox and label
        if track_id is None:
            bbox = item.get('bbox', [0, 0, 0, 0])
            # Create simple hash-based ID from bbox coordinates and label
            track_id = hash((label, int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))) % 10000
            print(f"No track_id found for {label}, using generated ID: {track_id}")
        
        if label:
            label_lower = label.lower()
            if 'person' in label_lower:
                detected_objects.append(('person', track_id))
                print(f"Person detected: {label} (Track ID: {track_id})")
            elif 'stair' in label_lower:
                detected_objects.append(('stairs', track_id))
                print(f"Stairs detected: {label} (Track ID: {track_id})")
            elif 'exit' in label_lower:
                detected_objects.append(('exit', track_id))
                print(f"Exit sign detected: {label} (Track ID: {track_id})")
            elif 'door' in label_lower:
                detected_objects.append(('door', track_id))
                print(f"Door detected: {label} (Track ID: {track_id})")

    return detected_objects

def main():
    """Main function to run the depth sensing and vibration feedback."""
    depth_model, detection_model = init_models()
    picam2 = init_picamera()
    
    # Initialize object tracker for detection model
    tracker = degirum_tools.ObjectTracker(
        track_thresh=0.3,
        anchor_point=degirum_tools.AnchorPoint.CENTER,
        show_overlay=True
    )

    with degirum_tools.Display("Depth Camera") as output_display:
        while True:
            frame = picam2.capture_array("main")
            
            # Run object detection for multiple object types
            detection_result = detection_model.predict(frame)
            
            # Apply tracking to the detection result
            tracker.analyze(detection_result)
            
            # Check for object detections and trigger vibrations in threads
            detected_objects = detect_objects(detection_result)
            for obj_type, track_id in detected_objects:
                vibration_thread = Thread(target=trigger_object_detection_vibration, args=(obj_type, track_id))
                vibration_thread.start()
            
            # Continue with depth processing
            depth_result = depth_model.predict(frame)

            # Process depth for vibration analysis
            depth_map = depth_processing(depth_result)
            
            # Generate display version only when needed (currently commented out)
            # depth_map_color = depth_for_display(depth_map)
            # output_display.show(depth_map_color)        

            avg_depths = depth_in_7_segments(depth_map)

            for i, avg_depth in enumerate(avg_depths):
                intensity = depth_map_to_vibrator(avg_depth)
                print(intensity)
                vibrate_thread = Thread(target=vibrate_motor, args=(intensity, drvs[i]))
                vibrate_thread.start()

if __name__ == "__main__":
    main()