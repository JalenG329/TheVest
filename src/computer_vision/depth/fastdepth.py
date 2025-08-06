import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

model = dg.load_model(
    model_name="fastdepth--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.set_controls({"FrameRate": 240})  # Set frame rate to 240 FPS
camera.start()

# Generate frames
def generate_frame():
    while True:
        frame = camera.capture_array()
        yield frame

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

        # Normalize to 0-255 for visualization
        depth_map_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
        depth_map_normalized = np.uint8(depth_map_normalized)

        depth_map_color = cv2.cvtColor(depth_map_normalized, cv2.COLOR_GRAY2BGR)

        output_display.show(depth_map_color)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()