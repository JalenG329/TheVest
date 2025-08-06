import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2

# Video source
def source():
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    camera.start()
    while True:
        frame = camera.capture_array("main")
        yield frame

model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

video_source = source()

with degirum_tools.Display("Object Detection Camera") as output_display:
    for result in model.predict_batch(video_source):
        output_display.show(result)
