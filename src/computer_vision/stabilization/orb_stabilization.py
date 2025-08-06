import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import collections
import time

last_print_time = 0
print_interval = .1  # seconds

xscale = 224 / 1280  # Width
yscale = 224 / 720   # Height

# Init camera
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.start()

# Init models
detection_model = dg.load_model(    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

depth_model = dg.load_model(
    model_name="depth_anything_v2--224x224_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

# ORB-based video stabilization setup
orb = cv2.ORB_create(2000)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

prev_gray = None
prev_kp = None
prev_des = None

with degirum_tools.Display("Detection to Depth Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        kp, des = orb.detectAndCompute(gray, None)

        # Stabilization
        if prev_gray is not None and prev_des is not None and des is not None and len(prev_kp) > 0 and len(kp) > 0:
            matches = bf.match(prev_des, des)
            matches = sorted(matches, key=lambda x: x.distance)
            if len(matches) > 200:
                src_pts = np.float32([prev_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                # m, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts)
                m, inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts, method=cv2.RANSAC)
                if m is not None:
                    stabilized_frame = cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
                else:
                    stabilized_frame = frame
            else:
                stabilized_frame = frame
        else:
            stabilized_frame = frame

        # Run detection model on stabilized frame
        detection_result = detection_model.predict(stabilized_frame)
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
                x_min = int(bbox[0] * xscale)
                y_min = int(bbox[1] * yscale)
                x_max = int(bbox[2] * xscale)
                y_max = int(bbox[3] * yscale)
                # Get the cropped depth map
                raw_data = depth_result._inference_results[0]['data']
                # Reshape to 2D (224x224)
                raw_data = raw_data.reshape((224, 224))
                # Crop the depth map using the scaled bounding box
                cropped_depth_map = raw_data[(y_min):(y_max), (x_min):(x_max)]
                # Get the average depth value
                average_depth = np.average(cropped_depth_map)
                # Set object depth string based on average depth
                # if 0 < average_depth < 20:
                #     string_depth = "far"
                # elif 20 <= average_depth < 40:
                #     string_depth = "close"
                # elif 40 <= average_depth:
                #     string_depth = "near"
                if label == "person":
                    print(f"Average depth for {label}: {average_depth:.2f}")
        output_display.show(detection_result)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        prev_gray = gray
        prev_kp = kp
        prev_des = des
cv2.destroyAllWindows()


