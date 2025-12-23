import degirum as dg
import degirum_tools
from degirum_tools import CombiningCompoundModel
from picamera2 import Picamera2
import cv2

camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (1920, 1080)}))
camera.start()

detector1 = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

detector2 = dg.load_model(
    model_name="starvision_yolov8m_hailo8--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
)

detector2.output_class_Set = {'doors'}

model = CombiningCompoundModel(detector1, detector2)

with degirum_tools.Display("Object Detect Image") as output_display:
        while True:
            frame = camera.capture_array()
            result = model.predict(frame)
            result._show_probabilities = True
            output_display.show(result)
