import degirum as dg
import degirum_tools
import cv2

# Path to the input video file
video_path = "videoplayback.mp4"  # Change this to your video file path

# Open video file
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print(f"Error: Could not open video file {video_path}")
    exit(1)

model = dg.load_model(
    model_name="starvision_yolov8m_hailo8--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models"
)

with degirum_tools.Display("Object Detection Video") as output_display:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        result = model.predict(frame)
        result._show_probabilities = True
        output_display.show(result)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
