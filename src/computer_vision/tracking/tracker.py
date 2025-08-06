import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2

# # Initialize Picamera2
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.start()

# load the model
model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

# create object tracker
tracker = degirum_tools.ObjectTracker(
    track_thresh=0.3,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=True
)

with degirum_tools.Display("Object Detection Camera") as output_display:
    while True:
        frame = camera.capture_array("main")
        result = model.predict(frame)
        tracker.analyze(result)
        img = result.image_overlay
        img = tracker.annotate(result, img)
        output_display.show(img)
        

