import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2

model = dg.load_model(
    model_name="ubuntu--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

with degirum_tools.Display("Object Detect Image") as output_display:
    # Load the image
    image_path = "4.jpg"  # Replace with your image path

    frame = cv2.imread(image_path)

    frame = cv2.resize(frame, (640, 640))

    
    if frame is None:
        print("Error: Could not read the image.")
    else:
        # Run detection model
        result = model.predict(frame)
        result._show_probabilities = True
        
        # Display the result
        output_display.show(result)
        
        # Wait for a key press to exit
        cv2.waitKey(0)
        cv2.destroyAllWindows()

