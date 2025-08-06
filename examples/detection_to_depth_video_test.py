import degirum as dg
import degirum_tools
import cv2
import numpy as np
import time

last_print_time = 0
print_interval = .1  # seconds

# Path to the input video file
video_path = "videoplayback.mp4"  # Change this to your video file path

# Open video file
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print(f"Error: Could not open video file {video_path}")
    exit(1)

# Init models
detection_model = dg.load_model(
    model_name="starvision_yolov8m_hailo8--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

depth_model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

with degirum_tools.Display("Detection to Depth Video") as output_display:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Run detection model
        detection_result = detection_model.predict(frame)
        # Run depth model
        depth_result = depth_model.predict(frame)
        # Optionally print or process results
        if detection_result._inference_results:
            for result in detection_result._inference_results:
                bbox = result['bbox']
                label = result['label']
                xscale = 224 / 1280
                yscale = 224 / 720
                x_min = int(bbox[0] * xscale)
                y_min = int(bbox[1] * yscale)
                x_max = int(bbox[2] * xscale)
                y_max = int(bbox[3] * yscale)
                raw_data = depth_result._inference_results[0]['data']
                raw_data = raw_data.reshape((224, 224))
                cropped_depth_map = raw_data[(y_min):(y_max), (x_min):(x_max)]
                average_depth = np.average(cropped_depth_map)
                print(f"Average depth for {label}: {average_depth:.2f} ")
        output_display.show(detection_result)
        # Wait to match the video's FPS (default 30fps)
        if cap.get(cv2.CAP_PROP_FPS) > 0:
            delay = int(1000 / cap.get(cv2.CAP_PROP_FPS))
        else:
            delay = 33  # fallback to ~30fps
        if cv2.waitKey(delay) & 0xFF == ord('q'):
            break
cv2.destroyAllWindows()
