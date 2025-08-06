import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

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
        
        

        # # Print quantization info and depth range
        # print(f"Quantization - Scale: {scale}, Zero: {zero}")
        # print(f"Raw data range: {raw_data.min()} to {raw_data.max()}")
        # print(f"Depth map range: {depth_map.min():.4f} to {depth_map.max():.4f}")
        
        # # Calculate theoretical range
        # raw_min, raw_max = 0, 255  # Typical uint8 range
        # theoretical_min = (raw_min - zero) * scale
        # theoretical_max = (raw_max - zero) * scale
        # print(f"Theoretical depth range: {theoretical_min:.4f} to {theoretical_max:.4f}")
        # print("---")

        # # Reshape to 2D (224x224)
        # depth_map = depth_map.reshape((224, 224))

        # # Normalize to 0-255 for visualization
        # depth_map_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
        # depth_map_normalized = np.uint8(depth_map_normalized)

        # depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)

        # output_display.show(depth_map_color)

        