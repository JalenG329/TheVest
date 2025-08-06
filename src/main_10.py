from unittest import result
import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2
import numpy as np
import math

import board
import busio

import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
import adafruit_drv2605

import time
from threading import Thread, Lock
import warnings

# Suppress numpy warnings that can occur in tracking
warnings.filterwarnings('ignore', category=RuntimeWarning)

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

# Smooth vibration parameters
RAMP_FACTOR = 0.4  # How fast intensity changes (0.1=slow, 0.9=fast)
HYSTERESIS_THRESHOLD = 0.08  # meters - prevents small fluctuations
INTENSITY_LEVELS = 8  # Number of distinguishable intensity levels
MIN_INTENSITY_CHANGE = 5  # Minimum change to update motor

drv1 = DRV2605(mux[1])  # Channel 1
drv2 = DRV2605(mux[3])  # Channel 3
drv3 = DRV2605(mux[6])  # Channel 6
drv4 = DRV2605(mux[5])  # Channel 5
drv5 = DRV2605(mux[4])  # Channel 4
drv6 = DRV2605(mux[7])  # Channel 7
drv7 = DRV2605(mux[2])  # Channel 2
drv8 = DRV2605(mux[0])  # Channel 0

drvs = [drv2, drv3, drv4, drv5, drv6, drv7, drv8]

# Global variables for temporal smoothing and smooth vibration
previous_depth_map = None
previous_avg_depths = None
current_avg_depths = None
current_intensities = [0, 0, 0, 0, 0, 0, 0]  # Current intensity for each motor
intensity_lock = Lock()  # Thread safety for intensity updates

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

def quantize_intensity(intensity, levels=INTENSITY_LEVELS):
    """Quantize intensity to a fixed number of distinguishable levels."""
    if intensity == 0:
        return 0
    step = 127 / (levels - 1)
    return int(round(intensity / step) * step)

def perceptual_mapping(depth_value, min_depth=0.5, max_depth=2.5):
    """Map depth using perceptual scaling (Stevens' power law)."""
    if depth_value >= max_depth:
        return 0
    if depth_value <= min_depth:
        return 127
    
    # Normalize to 0-1 range (inverted so closer = higher intensity)
    normalized = 1.0 - (depth_value - min_depth) / (max_depth - min_depth)
    
    # Stevens' power law with exponent 0.6 for vibration perception
    perceptual = math.pow(normalized, 0.6)
    
    return int(perceptual * 127)

def vibrate_motor_smooth(target_intensity, drv, motor_index):
    """Gradually change vibration intensity for smoother transitions."""
    global current_intensities
    
    with intensity_lock:
        current = current_intensities[motor_index]
        
        # Quantize target intensity for better distinguishability
        target_intensity = quantize_intensity(target_intensity)
        
        # Calculate new intensity with ramping (moving towards target)
        intensity_diff = target_intensity - current
        new_intensity = current + int(RAMP_FACTOR * intensity_diff)
        
        # Only update if intensity changed significantly
        if abs(new_intensity - current) >= MIN_INTENSITY_CHANGE or (new_intensity == 0 and current != 0):
            drv.mode = MODE_REALTIME
            drv.realtime_value = new_intensity
            current_intensities[motor_index] = new_intensity
            print(f"Motor {motor_index}: {current} -> {new_intensity} (target: {target_intensity})")

def depth_map_to_vibrator(depth_value, min_depth=0.5, max_depth=2.5, min_v=0, max_v=127):
    """Map depth value to vibration intensity using perceptual mapping for smooth feedback."""
    return perceptual_mapping(depth_value, min_depth, max_depth)

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
    """Divide depth map into 7 segments horizontally with hysteresis to prevent jitter."""
    global previous_depth_map, previous_avg_depths, current_avg_depths
    
    # Apply temporal smoothing if we have a previous frame
    if previous_depth_map is not None:
        depth_map = TEMPORAL_SMOOTHING_ALPHA * depth_map + (1 - TEMPORAL_SMOOTHING_ALPHA) * previous_depth_map
    
    height, width = depth_map.shape
    segment_width = width // 7
    new_avg_depths = []

    for i in range(7):
        segment = depth_map[:, i * segment_width:(i + 1) * segment_width]
        avg_depth = np.mean(segment)
        new_avg_depths.append(avg_depth)

    # Apply hysteresis - only update if change exceeds threshold
    if current_avg_depths is None:
        current_avg_depths = new_avg_depths.copy()
    else:
        for i in range(7):
            # Only update if change is significant enough
            if abs(new_avg_depths[i] - current_avg_depths[i]) > HYSTERESIS_THRESHOLD:
                current_avg_depths[i] = new_avg_depths[i]

    # Apply additional temporal smoothing to prevent rapid changes
    if previous_avg_depths is not None:
        smoothed_avg_depths = []
        for i in range(7):
            smoothed_depth = TEMPORAL_SMOOTHING_ALPHA * current_avg_depths[i] + (1 - TEMPORAL_SMOOTHING_ALPHA) * previous_avg_depths[i]
            smoothed_avg_depths.append(smoothed_depth)
        current_avg_depths = smoothed_avg_depths

    print(f"Average depths for segments: {[f'{d:.2f}' for d in current_avg_depths]}")

    # Store current values for next frame
    previous_depth_map = depth_map.copy()
    previous_avg_depths = current_avg_depths.copy()

    return current_avg_depths

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
    """Main function to run the depth sensing and vibration feedback with smooth haptic feedback."""
    depth_model, detection_model = init_models()
    picam2 = init_picamera()
    
    # Initialize object tracker for detection model with robust settings
    tracker = degirum_tools.ObjectTracker(
        track_thresh=0.5,  # Increased threshold for more stable tracking
        match_thresh=0.8,   # Higher matching threshold
        anchor_point=degirum_tools.AnchorPoint.CENTER,
        show_overlay=True
    )

    # Initialize current intensities
    global current_intensities
    current_intensities = [0] * 7

    print("Starting smooth haptic feedback system...")
    print(f"Intensity levels: {INTENSITY_LEVELS}, Ramp factor: {RAMP_FACTOR}")
    print(f"Hysteresis threshold: {HYSTERESIS_THRESHOLD}m")

    with degirum_tools.Display("Depth Camera") as output_display:
        while True:
            frame = picam2.capture_array("main")
            
            # Run object detection for multiple object types
            detection_result = detection_model.predict(frame)
            
            # Apply tracking to the detection result with error handling
            try:
                tracker.analyze(detection_result)
            except (ValueError, RuntimeWarning) as e:
                print(f"Tracker warning/error (continuing): {e}")
                # Continue without tracking for this frame
            
            # Check for object detections and trigger vibrations in threads
            detected_objects = detect_objects(detection_result)
            for obj_type, track_id in detected_objects:
                vibration_thread = Thread(target=trigger_object_detection_vibration, args=(obj_type, track_id))
                vibration_thread.start()
            
            # Continue with depth processing
            try:
                depth_result = depth_model.predict(frame)
                # Process depth for vibration analysis
                depth_map = depth_processing(depth_result)
                avg_depths = depth_in_7_segments(depth_map)

                # Update vibrations with smooth intensity changes
                for i, avg_depth in enumerate(avg_depths):
                    if not np.isnan(avg_depth) and not np.isinf(avg_depth):  # Check for valid depth values
                        target_intensity = depth_map_to_vibrator(avg_depth)
                        vibrate_thread = Thread(target=vibrate_motor_smooth, args=(target_intensity, drvs[i], i))
                        vibrate_thread.start()
                        
            except Exception as e:
                print(f"Depth processing error (continuing): {e}")
                # Continue to next frame if depth processing fails

            # Small delay to prevent thread congestion and allow smooth transitions
            time.sleep(0.05)

if __name__ == "__main__":
    main()
