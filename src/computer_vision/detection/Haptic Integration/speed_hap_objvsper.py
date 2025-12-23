# person_speed_haptic_test_v9_directional_multizone.py
# -----------------------------------------------------
# Same stable activation method as v7 (verified working)
# Adds distance-based waveform selection:
# - Object detection uses effects 47–51 (Buzz family)
# - Person detection uses effects 52–55 (Pulsing family)
# - C4 and C1 share central zone
# - Person overrides object in overlapping zones

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time
import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME
import adafruit_drv2605

# ------------------- CAMERA & MODEL SETUP -------------------
KNOWN_DISTANCE = 2.5       # meters
KNOWN_WIDTH = 0.4          # meters
FOCAL_LENGTH = None

camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (960, 540), "format": "RGB888"}))
camera.start()
time.sleep(2)

model = dg.load_model(
    model_name="yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    inference_host_address="@local",
    zoo_url="/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=False,
    overlay_show_probabilities=False
)

tracker = degirum_tools.ObjectTracker(
    track_thresh=0.4,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=False
)

# ------------------- I2C + HAPTIC DRIVER SETUP -------------------
i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

drv_channels = [mux[i] for i in [1, 2, 3, 4, 5, 6, 7]]
drvs = []

print("🔧 Initializing DRV2605 channels...")
for idx, ch in enumerate(drv_channels):
    try:
        time.sleep(0.2)
        drv = DRV2605(ch)
        drv.mode = MODE_REALTIME
        drv.realtime_value = 0
        drvs.append(drv)
        print(f"✅ DRV2605 initialized on channel {idx+1}")
    except OSError as e:
        print(f"⚠️ Skipping channel {idx+1}: DRV not detected ({e})")

# ------------------- FRAME SEGMENT TO MOTOR MAPPING -------------------
frame_width = 960
segments = [
    (0, 120, ["C3"]),
    (120, 240, ["C6"]),
    (240, 360, ["C5"]),
    (360, 480, ["C4", "C1"]),
    (480, 600, ["C7"]),
    (600, 720, ["C2"]),
    (720, 960, ["C0"])
]

motor_map = {
    "C0": 0, "C1": 1, "C2": 2, "C3": 3,
    "C4": 4, "C5": 5, "C6": 6, "C7": 7
}


def get_motors_for_bbox(x1, x2):
    """Return all motors corresponding to horizontal span of the bounding box."""
    motors = set()
    for (x_min, x_max, motor_labels) in segments:
        if x2 > x_min and x1 < x_max:
            for m in motor_labels:
                if motor_map[m] < len(drvs):
                    motors.add(drvs[motor_map[m]])
    return list(motors)

# ------------------- DISTANCE HELPERS -------------------


def compute_focal_length(known_distance, real_width, width_in_image):
    return (width_in_image * known_distance) / real_width


def compute_distance(focal_length, real_width, width_in_image):
    if width_in_image <= 0:
        return None
    return (real_width * focal_length) / width_in_image


def map_distance_to_intensity(distance):
    """Convert distance to realtime intensity value."""
    if distance is None:
        return 0
    if distance > 4:
        return 0
    elif distance > 3:
        return 40
    elif distance > 1:
        return 80
    else:
        return 127


def map_distance_to_effect(label, distance):
    """Choose waveform ID from distance (based on DRV2605 effect list)."""
    if distance is None:
        return 0

    # OBJECT: Buzz 1–2 family (47–51)
    if label != "person":
        if distance > 3:
            return 51  # Buzz 2 – 20%
        elif distance > 2:
            return 50  # Buzz 2 – 40%
        elif distance > 1:
            return 49  # Buzz 2 – 60%
        else:
            return 47  # Buzz 1 – 100%

    # PERSON: Pulsing strong/medium (52–55)
    else:
        if distance > 3:
            return 55  # Pulsing medium 2 – 60%
        elif distance > 2:
            return 54  # Pulsing medium 1 – 100%
        elif distance > 1:
            return 53  # Pulsing strong 2 – 60%
        else:
            return 52  # Pulsing strong 1 – 100%


# ------------------- HAPTIC FEEDBACK (with rate limiting) -------------------
last_update_time = 0
UPDATE_INTERVAL = 0.6  # seconds between I2C writes


def safe_haptic_update(callback, *args):
    global last_update_time
    now = time.time()
    if now - last_update_time >= UPDATE_INTERVAL:
        try:
            callback(*args)
        except OSError as e:
            print(f"⚠️ I2C write error during haptic update: {e}")
        last_update_time = now


def haptic_pattern(motors, intensity, effect_id):
    """Activate motor pattern with variable intensity and waveform."""
    for drv in motors:
        drv.mode = MODE_REALTIME
        drv.realtime_value = int(intensity)
        drv.sequence[0] = adafruit_drv2605.Effect(effect_id)
        drv.play()


def stop_all_motors():
    """Stops vibration for all connected DRV motors."""
    for drv in drvs:
        try:
            drv.mode = MODE_REALTIME
            drv.realtime_value = 0
        except Exception as e:
            print(f"⚠️ Failed to stop motor: {e}")


# ------------------- CALIBRATION -------------------
print("Place a person at 2.5 meters for calibration...")
time.sleep(3)

ref_frame = camera.capture_array("main")
ref_result = model.predict(ref_frame)
ref_width = 0
for det in ref_result.results:
    if det.get("label", "").lower() == "person":
        x1, y1, x2, y2 = det["bbox"]
        ref_width = x2 - x1
        break

if ref_width == 0:
    print("❌ No person detected for calibration.")
    camera.close()
    exit()

FOCAL_LENGTH = compute_focal_length(KNOWN_DISTANCE, KNOWN_WIDTH, ref_width)
print(f"✅ Calibrated focal length: {FOCAL_LENGTH:.2f} px")

# ------------------- MAIN LOOP -------------------
person_history = {}

with degirum_tools.Display("Directional Multi-Zone Haptics v9") as disp:
    print("Running... Press 'q' to quit.")
    frame_count = 0
    start_time = time.time()

    while True:
        frame = camera.capture_array("main")
        result = model.predict(frame)
        tracker.analyze(result)
        img = tracker.annotate(result, result.image_overlay)

        frame_count += 1
        if frame_count % 10 == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed
            print(f"📸 Current FPS: {fps:.2f}")

        if not result.results:
            stop_all_motors()
            disp.show(img)
            continue

        zone_activations = {}

        for det in result.results:
            label = det.get("label", "").lower()
            x1, y1, x2, y2 = det["bbox"]
            motors = get_motors_for_bbox(x1, x2)

            if not motors:
                continue

            width_in_pixels = x2 - x1
            distance_now = compute_distance(
                FOCAL_LENGTH, KNOWN_WIDTH, width_in_pixels)
            time_now = time.time()

            for m in motors:
                if label == "person" or m not in zone_activations:
                    zone_activations[m] = (label, distance_now, time_now)

        # Apply feedback patterns
        for m, (label, distance, _) in zone_activations.items():
            intensity = map_distance_to_intensity(distance)
            effect_id = map_distance_to_effect(label, distance)
            safe_haptic_update(haptic_pattern, [m], intensity, effect_id)

        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
