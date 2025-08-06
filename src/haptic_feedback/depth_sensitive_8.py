import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

import time
import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG
from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

# Initialize all 8 DRV2605 haptic drivers on different mux channels
drivers = []
for channel in range(8):
    try:
        drv = DRV2605(mux[channel])
        drivers.append(drv)
    except Exception as e:
        print(f"Failed to initialize driver on channel {channel}: {e}")
        drivers.append(None)

def map_depth_to_vibrator(depth, min_d, max_d, min_v, max_v):
    if max_d == min_d:
        return min_v
    return int(min_v + (depth - min_d) * (max_v - min_v) / (max_d - min_d))

def vibrate_motor_grid(depth_values, min_depth=18.91, max_depth=79.79, min_v=0, max_v=127):
    """Vibrate motors in a 2x4 grid based on depth values from corresponding tiles"""
    for i, depth_value in enumerate(depth_values):
        if i >= len(drivers) or drivers[i] is None:
            continue
        
        try:
            drivers[i].mode = MODE_REALTIME
            mapped_value = map_depth_to_vibrator(depth_value, min_depth, max_depth, min_v, max_v)
            drivers[i].realtime_value = mapped_value
        except Exception as e:
            print(f"Error setting vibration for motor {i}: {e}")
    
    time.sleep(1 / 30)  # based on fps
    
    # Stop all motors
    for i, drv in enumerate(drivers):
        if drv is not None:
            try:
                drv.realtime_value = 0
                drv.mode = MODE_INTTRIG
            except Exception as e:
                print(f"Error stopping motor {i}: {e}")

def extract_tile_depths(depth_map, rows=2, cols=4):
    """Extract average depth values from a 2x4 grid of tiles"""
    h, w = depth_map.shape
    tile_h = h // rows
    tile_w = w // cols
    
    tile_depths = []
    for row in range(rows):
        for col in range(cols):
            start_h = row * tile_h
            end_h = (row + 1) * tile_h if row < rows - 1 else h
            start_w = col * tile_w
            end_w = (col + 1) * tile_w if col < cols - 1 else w
            
            tile = depth_map[start_h:end_h, start_w:end_w]
            avg_depth = np.mean(tile)
            tile_depths.append(avg_depth)
    
    return tile_depths

model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.start()

with degirum_tools.Display("Depth Camera") as output_display:
    while True:
        frame = camera.capture_array()
        result = model.predict(frame)

        # Extract the raw data
        raw_data = result._inference_results[0]['data']

        # Dequantize the data
        scale = result._inference_results[0]['quantization']['scale'][0]
        zero = result._inference_results[0]['quantization']['zero'][0]
        depth_map = (raw_data.astype(np.float32) - zero) * scale

        # Reshape to 2D (224x224)
        depth_map = depth_map.reshape((224, 224))

        # Extract depth values for each tile in 2x4 grid
        tile_depths = extract_tile_depths(depth_map)

        # Start vibration thread with the tile depth values
        vibrate_thread = Thread(target=vibrate_motor_grid, args=(tile_depths,))
        vibrate_thread.start()

        # Normalize to 0-255 for visualization
        depth_map_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
        depth_map_normalized = np.uint8(depth_map_normalized)

        depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)
        
        # Draw grid lines to visualize the tiles
        h, w = depth_map_color.shape[:2]
        tile_h = h // 2
        tile_w = w // 4
        
        # Draw horizontal lines
        for row in range(1, 2):
            y = row * tile_h
            cv2.line(depth_map_color, (0, y), (w, y), (255, 255, 255), 2)
        
        # Draw vertical lines
        for col in range(1, 4):
            x = col * tile_w
            cv2.line(depth_map_color, (x, 0), (x, h), (255, 255, 255), 2)
        
        # Add text labels for each tile with depth values
        for row in range(2):
            for col in range(4):
                idx = row * 4 + col
                if idx < len(tile_depths):
                    center_x = col * tile_w + tile_w // 2
                    center_y = row * tile_h + tile_h // 2
                    depth_text = f"M{idx}: {tile_depths[idx]:.1f}"
                    cv2.putText(depth_map_color, depth_text, (center_x - 50, center_y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        output_display.show(depth_map_color)