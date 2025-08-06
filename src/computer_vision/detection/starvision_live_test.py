import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2

# # Initialize Picamera2
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888", "size": (1280, 720)}))
camera.start()

model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

with degirum_tools.Display("Object Detection Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        result = model.predict(frame)
        result._show_probabilities = True
        output_display.show(result)
        

cv2.destroyAllWindows()
