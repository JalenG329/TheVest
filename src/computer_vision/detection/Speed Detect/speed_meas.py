# person_speed_distance_rpi.py
# ----------------------------
# Estimate real-world speed (m/s) of detected persons using YOLO + distance tracking

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time

# ---- Known constants ----
KNOWN_DISTANCE = 2.5   # meters (for focal length calibration)
KNOWN_WIDTH = 0.4      # meters (average shoulder width of a person)
FOCAL_LENGTH = None    # to be calibrated

# ---- Initialize Camera ----
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (1280, 720), "format": "RGB888"}))
picam2.start()
time.sleep(2)

# ---- Load YOLO model ----
model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

# ---- Initialize tracker ----
tracker = degirum_tools.ObjectTracker(
    track_thresh=0.4,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=True
)

# ---- Helper functions ----


def compute_focal_length(known_distance, real_width, width_in_image):
    """Calibrate focal length based on a known distance and object width."""
    return (width_in_image * known_distance) / real_width


def compute_distance(focal_length, real_width, width_in_image):
    """Estimate distance in meters using calibrated focal length."""
    if width_in_image <= 0:
        return None
    return (real_width * focal_length) / width_in_image


# ---- Step 1: Calibrate focal length ----
print("Place a person at 2.5 meters for calibration...")
time.sleep(3)

ref_frame = picam2.capture_array("main")
ref_result = model.predict(ref_frame)

ref_width = 0
for det in ref_result.results:
    if det.get("label", "").lower() == "person":
        x1, y1, x2, y2 = det["bbox"]
        ref_width = x2 - x1
        break

if ref_width == 0:
    print("❌ No person detected for calibration. Try again.")
    picam2.close()
    exit()

FOCAL_LENGTH = compute_focal_length(KNOWN_DISTANCE, KNOWN_WIDTH, ref_width)
print(f"✅ Calibrated focal length: {FOCAL_LENGTH:.2f} px")

# ---- Step 2: Measure distance + compute speed ----
person_history = {}  # {track_id: (prev_distance, prev_time)}

print("Starting distance and speed estimation... Press 'q' to quit.")

with degirum_tools.Display("Person Distance + Speed") as output_display:
    while True:
        frame = picam2.capture_array("main")
        result = model.predict(frame)

        tracker.analyze(result)
        img = tracker.annotate(result, result.image_overlay)

        for det in result.results:
            if det.get("label", "").lower() == "person":
                track_id = det.get("track_id", None)
                if track_id is None:
                    continue

                x1, y1, x2, y2 = det["bbox"]
                width_in_pixels = x2 - x1
                distance_now = compute_distance(
                    FOCAL_LENGTH, KNOWN_WIDTH, width_in_pixels)
                time_now = time.time()

                if track_id in person_history:
                    prev_distance, prev_time = person_history[track_id]
                    dt = time_now - prev_time

                    if dt > 0 and prev_distance is not None and distance_now is not None:
                        speed = abs(distance_now - prev_distance) / dt  # m/s
                        direction = "Approaching" if distance_now < prev_distance else "Receding"

                        # Display distance and speed
                        text = f"{distance_now:.2f} m | {speed:.2f} m/s {direction}"
                        cv2.putText(img, text, (int(x2)-20, int(y1) + 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Update tracking data
                person_history[track_id] = (distance_now, time_now)

        output_display.show(img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

picam2.close()
cv2.destroyAllWindows()
