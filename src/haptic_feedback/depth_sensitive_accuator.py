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
drv = DRV2605(mux[3])  # Use channel 3 for the haptic driver

def vibrate_motor(depth_value, min_depth=18.91, max_depth=79.79, min_v=0, max_v=127):
    drv.mode = MODE_REALTIME

    # Map depth value to a range suitable for vibration intensity
    def map_depth_to_vibrator(depth, min_d, max_d, min_v, max_v):
        if max_d == min_d:
            return min_v
        return int(min_v + (depth - min_d) * (max_v - min_v) / (max_d - min_d))

    mapped_value = map_depth_to_vibrator(depth_value, min_depth, max_depth, min_v, max_v)
    drv.realtime_value = mapped_value
    time.sleep(1 / 30) # based on fps
    drv.realtime_value = 0
    drv.mode = MODE_INTTRIG

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
        depth_value = np.average(raw_data)

        # Start vibration thread with the depth value
        vibrate_thread = Thread(target=vibrate_motor, args=(int(depth_value),))
        vibrate_thread.start()


        # Dequantize the data
        scale = result._inference_results[0]['quantization']['scale'][0]
        zero = result._inference_results[0]['quantization']['zero'][0]
        depth_map = (raw_data.astype(np.float32) - zero) * scale

        # Reshape to 2D (224x224)
        depth_map = depth_map.reshape((224, 224))

        # Resize to 720x1280 for display
        depth_map = cv2.resize(depth_map, (1280, 720), interpolation=cv2.INTER_LINEAR)

        # Normalize to 0-255 for visualization
        depth_map_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
        depth_map_normalized = np.uint8(depth_map_normalized)

        depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)

        output_display.show(depth_map_color)