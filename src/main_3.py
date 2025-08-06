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

import time
from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

SCALE = (224/1280, 224/720)  # (x_scale, y_scale)
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

DELAY = 1 / 30  # Delay between intensity changes

def vibrate_motor(intensity, drv, delay=DELAY):
    drv.mode = MODE_REALTIME
    drv.realtime_value = intensity  # Set to desired intensity
    time.sleep(delay)  # Vibrate for specified delay
    drv.realtime_value = 0
    drv.mode = MODE_INTTRIG


def depth_map_to_vibrator(depth_value, min_depth=.5, max_depth=3.5, min_v=0, max_v=127):
    """Map depth value to a range suitable for vibration intensity."""
    if max_depth == min_depth:
        return min_v
    return int(min_v + (depth_value - min_depth) * (max_v - min_v) / (max_depth - min_depth))

def init_models():
    """Initialize and return combined detection model and depth model."""
    depth_model = dg.load_model("depth_anything_v2--224x224_quant_hailort_hailo8_1", "@local",
                               "/home/rohan/degirum_wearable_device/models")
    return depth_model

def init_picamera():
    """Initialize and return Picamera2 instance."""
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"size": (1280, 720)}))
    picam2.start()
    return picam2

def depth_output(depth_result):
    """Convert depth result to a displayable format with denoising."""
    raw_data = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    depth_map = (raw_data.astype(np.float32) - zero) * scale
    depth_map = depth_map.reshape((224, 224))
    
    # Apply Gaussian blur for spatial denoising
    depth_map_denoised = cv2.GaussianBlur(depth_map, (GAUSSIAN_KERNEL_SIZE, GAUSSIAN_KERNEL_SIZE), GAUSSIAN_SIGMA)
    
    # Resize to 720x1280 for display
    resized_depth_map = cv2.resize(depth_map_denoised, (1280, 720), interpolation=cv2.INTER_LINEAR)

    # Normalize to 0-255 for visualization
    depth_map_normalized = cv2.normalize(resized_depth_map, None, 0, 255, cv2.NORM_MINMAX)
    depth_map_normalized = np.uint8(depth_map_normalized)

    depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)
    return depth_map_color, depth_map_denoised

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

def main():
    """Main function to run the depth sensing and vibration feedback."""
    depth_model = init_models()
    picam2 = init_picamera()

    with degirum_tools.Display("Depth Camera") as output_display:
        while True:
            frame = picam2.capture_array("main")
            depth_result = depth_model.predict(frame)

            depth_map_color, depth_map = depth_output(depth_result)
            # output_display.show(depth_map_color)        

            avg_depths = depth_in_7_segments(depth_map)

            for i, avg_depth in enumerate(avg_depths):
                intensity = depth_map_to_vibrator(avg_depth)
                vibrate_thread = Thread(target=vibrate_motor, args=(intensity, drvs[i]))
                vibrate_thread.start()

if __name__ == "__main__":
    main()