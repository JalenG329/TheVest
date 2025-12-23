import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import time

# Initialize Picamera2
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"format": "RGB888"}))
camera.start()

# Load the model
model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

# Create object tracker
tracker = degirum_tools.ObjectTracker(
    track_thresh=0.3,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=True
)

# History for speed calculation {track_id: (x, y, t)}
object_history = {}

with degirum_tools.Display("Object Detection + Speed") as output_display:
    while True:
        frame = camera.capture_array("main")
        result = model.predict(frame)

        # Assign tracker IDs
        tracker.analyze(result)

        # Annotated image from tracker
        img = result.image_overlay
        img = tracker.annotate(result, img)

        # Loop through detections
        for det in result.results:
            track_id = det.get("track_id", None)
            bbox = det.get("bbox", None)
            label = det.get("label", "object")

            if track_id is None or bbox is None:
                continue

            # bbox format: [x1, y1, x2, y2]
            x1, y1, x2, y2 = bbox
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            t_now = time.time()

            if track_id in object_history:
                prev_x, prev_y, prev_t = object_history[track_id]
                dt = max(t_now - prev_t, 1e-6)
                dx = center_x - prev_x
                dy = center_y - prev_y
                vx = dx / dt
                vy = dy / dt
                speed = (vx**2 + vy**2) ** 0.5  # px/sec

                # Draw speed text on image above bounding box
                speed_text = f"{label} {speed:.1f} px/s"
                cv2.putText(
                    img,
                    speed_text,
                    (int(x2)-25, int(y1) - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 69, 255),
                    2
                )

            # Update history
            object_history[track_id] = (center_x, center_y, t_now)

        # Show the image
        output_display.show(img)
