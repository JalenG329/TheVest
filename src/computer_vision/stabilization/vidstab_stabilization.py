import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import collections
from vidstab import VidStab
import time

last_print_time = 0
print_interval = 2  # seconds

# Init camera
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
camera.start()

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

# Initialize VidStab stabilizer
stabilizer = VidStab()

def stabilize_frame_thread(input_frame, output_queue):
    """
    Thread function to stabilize frames using VidStab.
    """
    stabilized_frame = stabilizer.stabilize_frame(input_frame=input_frame, border_size=20)
    if stabilized_frame is None:
        stabilized_frame = input_frame  # Use original if stabilization not ready
    output_queue.append(stabilized_frame)

with degirum_tools.Display("Detection to Depth Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        # Stabilize the frame using VidStab
        stabilized_frame = stabilizer.stabilize_frame(input_frame=frame, border_size=20)
        if stabilized_frame is None:
            stabilized_frame = frame  # Use original if stabilization not ready

        # Run detection model on stabilized frame
        detection_result = detection_model.predict(stabilized_frame)
        
        # For slowing prints
        current_time = time.time()
        should_print = current_time - last_print_time >= print_interval
        if detection_result._inference_results and should_print:
            last_print_time = current_time
            # Run depth model on stabilized frame
            depth_result = depth_model.predict(stabilized_frame)
            for result in detection_result._inference_results:
                
                bbox = result['bbox']
                label = result['label']

                # Correct scaling from original frame (1280x720) to 224x224
                xscale = 224 / 1280  # Width
                yscale = 224 / 720   # Height

                x_min = int(bbox[0] * xscale)
                y_min = int(bbox[1] * yscale)
                x_max = int(bbox[2] * xscale)
                y_max = int(bbox[3] * yscale)

                # Get the cropped depth map
                raw_data = depth_result._inference_results[0]['data']            

                # Reshape to 2D (224x224)
                raw_data = raw_data.reshape((224, 224))
                # Crop the depth map using the scaled bounding box
                cropped_depth_map = raw_data[
                    (y_min):(y_max), (x_min):(x_max)
                ]

                # Get the average depth value
                average_depth = np.average(cropped_depth_map)

                # Set object depth string based on average depth
                if 0 < average_depth < 20:
                    string_depth = "far"
                elif 20 <= average_depth < 40:
                    string_depth = "close"
                elif 40 <= average_depth:
                    string_depth = "near"

                print(f"Average depth for {label}: {string_depth}")
        output_display.show(detection_result)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
cv2.destroyAllWindows()