import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

# Denoising parameters
GAUSSIAN_KERNEL_SIZE = 5
GAUSSIAN_SIGMA = 1.5
TEMPORAL_SMOOTHING_ALPHA = 0.3  # Lower values = more smoothing

model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (1280, 720)}))
camera.start()

# Generate frames
def generate_frame():
    while True:
        frame = camera.capture_array()
        yield frame

# Add a buffer for temporal smoothing
previous_depth_map = None

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

        # Apply Gaussian blur for spatial denoising
        depth_map_denoised = cv2.GaussianBlur(depth_map, (GAUSSIAN_KERNEL_SIZE, GAUSSIAN_KERNEL_SIZE), GAUSSIAN_SIGMA)

        # Apply temporal smoothing if we have a previous frame
        if previous_depth_map is not None:
            depth_map_smoothed = TEMPORAL_SMOOTHING_ALPHA * depth_map_denoised + (1 - TEMPORAL_SMOOTHING_ALPHA) * previous_depth_map
        else:
            depth_map_smoothed = depth_map_denoised

        # Store current frame for next iteration
        previous_depth_map = depth_map_smoothed.copy()

        # Resize to 720p (1280x720) for display
        depth_map_resized = cv2.resize(depth_map_smoothed, (1280, 720), interpolation=cv2.INTER_LINEAR)

        # Normalize to 0-255 for visualization
        depth_map_normalized = cv2.normalize(depth_map_resized, None, 0, 255, cv2.NORM_MINMAX)
        depth_map_normalized = np.uint8(depth_map_normalized)

        # Apply color map for better visualization
        depth_map_color = cv2.applyColorMap(depth_map_normalized, cv2.COLORMAP_TURBO)

        output_display.show(depth_map_color)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()