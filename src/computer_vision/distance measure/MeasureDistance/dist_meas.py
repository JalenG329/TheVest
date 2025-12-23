# person_distance_yolo_rpi.py
# ---------------------------
# Estimate distance of detected persons using Hailo YOLO + Raspberry Pi Camera

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time

# ---- Known constants ----
# meters (distance to reference person during calibration)
KNOWN_DISTANCE = 2.5
KNOWN_WIDTH = 0.4      # meters (average shoulder width of a person)
FOCAL_LENGTH = None    # Will be calibrated

# ---- Initialize Camera ----
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (1280, 720), "format": "RGB888"}))
picam2.start()
time.sleep(2)

# ---- Load YOLO model (Hailo runtime) ----
model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=True,
    overlay_show_probabilities=True
)

# ---- Helper functions ----


def compute_focal_length(known_distance, real_width, width_in_image):
    """Calibrate focal length based on a known distance and object width."""
    return (width_in_image * known_distance) / real_width


def compute_distance(focal_length, real_width, width_in_image):
    """Estimate distance using the calibrated focal length."""
    if width_in_image <= 0:
        return None
    return (real_width * focal_length) / width_in_image


# ---- Step 1: Calibrate focal length ----
print("Place a person at 2.5 meter distance for calibration...")
time.sleep(3)

ref_frame = picam2.capture_array("main")
ref_result = model.predict(ref_frame)

# Find the first detected 'person'
ref_width = 0
for det in ref_result.results:
    if det.get("label", "").lower() == "person":
        x1, y1, x2, y2 = det["bbox"]
        ref_width = x2 - x1
        break

if ref_width == 0:
    print("❌ No person detected in calibration frame. Try again.")
    picam2.close()
    exit()

FOCAL_LENGTH = compute_focal_length(KNOWN_DISTANCE, KNOWN_WIDTH, ref_width)
print(f"✅ Calibrated focal length: {FOCAL_LENGTH:.2f} px")

# ---- Step 2: Continuous Distance Measurement ----
print("Starting distance estimation... Press 'q' to quit.")

with degirum_tools.Display("Person Distance Estimation") as output_display:
    while True:
        frame = picam2.capture_array("main")
        result = model.predict(frame)

        for det in result.results:
            if det.get("label", "").lower() == "person":
                x1, y1, x2, y2 = det["bbox"]
                width_in_pixels = x2 - x1
                distance = compute_distance(
                    FOCAL_LENGTH, KNOWN_WIDTH, width_in_pixels)

                # Draw detection box + distance label
                cv2.rectangle(frame, (int(x1), int(y1)),
                              (int(x2), int(y2)), (0, 255, 0), 2)
                if distance:
                    cv2.putText(frame, f"{distance:.2f} m",
                                (int(x2)-10, int(y1) + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        output_display.show(frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

picam2.close()
cv2.destroyAllWindows()
