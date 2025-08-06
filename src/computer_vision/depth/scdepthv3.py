import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np

model = dg.load_model(
    model_name="scdepthv3--320x256_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.start()

# Generate frames
def generate_frame():
    while True:
        frame = camera.capture_array()
        yield frame

# Run inference and display
for result in model.predict_batch(generate_frame()):

    # # Print the result for debugging
    # #print(result._inference_results)

    # Extract the raw data
    raw_data = result._inference_results[0]['data']

    # min = np.min(raw_data)
    # max = np.max(raw_data)
    # For debugging purposes
    # print(f"Raw data min: {min}, max: {max}")

    # Dequantize the data
    scale = result._inference_results[0]['quantization']['scale'][0]
    zero = result._inference_results[0]['quantization']['zero'][0]
    depth_map = (raw_data.astype(np.float32) - zero) * scale

    # min = np.min(depth_map)
    # max = np.max(depth_map)
    # For debugging purposes
    # print(f"Depth map min: {min}, max: {max}")
    # Depth map min: 2.609717607498169, max: 5.189956188201904

    # Reshape to 2D (256x320)
    depth_map = depth_map.reshape((256, 320))

    # Normalize to 0-255 for visualization
    depth_map_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)

    depth_map_normalized = np.uint8(depth_map_normalized)

    # brightness_offset = 50  # Adjust this value to increase or decrease brightness

    # brightened_image = cv2.convertScaleAbs(depth_map_normalized, alpha=1, beta=brightness_offset)

    cv2.imshow("Object Detection Camera", depth_map_normalized)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
cv2.destroyAllWindows()