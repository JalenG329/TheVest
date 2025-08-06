import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2

# Load the model
model = dg.load_model(
    model_name="ubuntu--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)
camera = Picamera2()
camera.configure(camera.create_preview_configuration(main={"format": "RGB888"}))
camera.start()

# Generate frames
def generate_frame():
    
    while True:
        frame = camera.capture_array()
        yield frame

# Run inference and display
for result in model.predict_batch(generate_frame()):
    cv2.imshow("Object Detection Camera", result.image_overlay)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
