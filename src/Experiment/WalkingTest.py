# haptic_object_distance_trials.py
# ---------------------------------------------------------
# Distance-only haptic experiment script
#
# Trial behavior:
#   Press 't'
#   7 seconds: silent object placement
#   5 seconds: buzzing based on detected distance
#   Motors stop after trial
# ---------------------------------------------------------

import time # for timing control
import threading    # for motor control loop
import atexit   # for cleanup on exit
import signal   # for handling Ctrl+C
import sys  # for sys.exit
from collections import deque   # for smoothing buffers

import cv2  # for image processing and preview
from ultralytics import YOLO    # for object detection
from picamera2 import Picamera2 # for camera access

import board    # for I2C
import busio    # for I2C
import adafruit_tca9548a    # for I2C multiplexing
from adafruit_drv2605 import DRV2605, MODE_REALTIME # for motor control


# ===================== CONFIG =====================

MODEL_PATH = "yolo11n.pt"   # YOLO model file (make sure this is in the correct path)
# Detect only large/meaningful obstacle classes.
# NOTE: standard YOLO COCO models do not include a true "box" class.
# "suitcase" is used as the closest built-in proxy for a box-like obstacle.
TARGET_CLASSES = {"chair", "person", "suitcase"}
DISPLAY_NAMES = {"suitcase": "box"}    # Object class to detect (must be in YOLO model)

CAM_W = 960 # camera resolution width
CAM_H = 720 # camera resolution height
SHOW_PREVIEW = True # set to True to see camera feed with detections (useful for debugging, can be set to False for better performance)

# Trial timing
PLACEMENT_TIME = 7.0    # seconds for user to place object without feedback
BUZZ_TIME = 5.0      # seconds to buzz based on detected distance
TRIAL_PAUSE_TIME = 1.0  # seconds to wait after trial before allowing another

# Detection tuning
CONF_THRESHOLD = 0.25    # minimum confidence for detection to be considered valid
MIN_BBOX_HEIGHT = 25    # minimum bounding box height in pixels to filter out small detections (noise)
STALE_TIMEOUT = 0.45    # seconds to wait after last detection before stopping motors (if trial is active)

UPDATE_INTERVAL = 0.01  # seconds between motor updates (controls vibration rhythm)

# Distance settings
CALIBRATION_DISTANCE_M = 5.0    # the real-world distance (in meters) that corresponds to the calibration bounding box height (user sets this by placing object at this distance and pressing 's')
MIN_DISTANCE_M = 0.5      # minimum distance to detect (anything closer than this is considered at max intensity)
MAX_DISTANCE_M = 4.0    # maximum distance to detect (anything farther than this is considered no vibration)

# Smoothing
HEIGHT_HISTORY = 6  # how many recent bounding box heights to average for distance calculation
DIST_HISTORY = 5    # how many recent distance estimates to average for stable output
DIST_EMA_ALPHA = 0.30   # EMA alpha for distance (vibration strength) - higher = more responsive, lower = smoother

# Vibration intensity levels
INTENSITY_LEVELS = {
    1: 20,
    2: 45,
    3: 70,
    4: 105,
    5: 127,
}

# All motors used for distance-only feedback
ALL_MOTORS_RAW = [0, 1, 2, 3, 4, 5, 6, 7]


# ===================== GLOBAL STATE =====================

drivers = {}             # stores motor drivers
available_channels = set()  # which channels are actually working (for calibration feedback)

picam2 = None   # camera instance
model = None    # AI model instance

calibrated = False  # has user done distance calibration yet? (calibration is done by placing object at known distance and pressing 's')
calibration_height = None   # pixel height of bounding box at calibration distance (used to convert future heights to distance)

height_buffer = deque(maxlen=HEIGHT_HISTORY)    # recent bounding box heights for distance calculation (used to smooth out noise in height measurements before converting to distance)
distance_buffer = deque(maxlen=DIST_HISTORY)    # recent distance estimates for stable output (used to smooth out noise in distance estimates before converting to vibration intensity)

state_lock = threading.Lock()   # protects access to shared state (haptic output settings)

haptic_state = {
    "channels": [],
    "intensity": 0,
    "pulse_on": 0.22,
    "pulse_off": 0.30,
    "last_seen": 0.0,
    "running": True,
    "trial_active": False,
}

track_state = {
    "distance_m": None,
}


# ===================== HELPERS =====================

def clamp(value, low, high):    
    return max(low, min(high, value))


def ema(previous_value, new_value, alpha):
    if previous_value is None:
        return new_value
    return alpha * new_value + (1.0 - alpha) * previous_value


def all_motors_off():
    for drv in drivers.values():
        if drv:
            drv.realtime_value = 0


# ===================== DISTANCE =====================

def height_to_distance_m(height_px):
    if not calibrated or calibration_height is None:
        return None

    if height_px <= 0:
        return None

    a = CALIBRATION_DISTANCE_M * calibration_height
    distance = a / float(height_px)

    return clamp(distance, MIN_DISTANCE_M, MAX_DISTANCE_M)


def get_distance_level(distance_m):
    if distance_m is None or distance_m > MAX_DISTANCE_M:
        return 0
    elif distance_m <= 1.0:
        return 5
    elif distance_m <= 1.75:
        return 4
    elif distance_m <= 2.5:
        return 3
    elif distance_m <= 3.25:
        return 2
    else:
        return 1


def distance_to_intensity(distance_m):
    level = get_distance_level(distance_m)
    return INTENSITY_LEVELS.get(level, 0)


def distance_to_pulse(distance_m):
    level = get_distance_level(distance_m)

    if level == 0:
        return 0.18, 0.40
    elif level == 1:
        return 0.12, 0.36
    elif level == 2:
        return 0.14, 0.28
    elif level == 3:
        return 0.16, 0.22
    elif level == 4:
        return 0.18, 0.16
    else:
        return 0.22, 0.08


# ===================== DETECTION =====================

def find_best_target(results):
    best_box = None
    best_label = None
    best_score = 0

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]

            if label not in TARGET_CLASSES:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            height = y2 - y1

            if conf < CONF_THRESHOLD:
                continue

            if height < MIN_BBOX_HEIGHT:
                continue

            # Prefer confident, larger objects because they are usually
            # closer and more important for walking safety.
            score = conf * height

            if score > best_score:
                best_score = score
                best_box = box
                best_label = label

    return best_box, best_label

# ===================== MOTOR LOOP =====================

def motor_loop():
    while True:
        with state_lock:
            running = haptic_state["running"]
            channels = list(haptic_state["channels"])
            intensity = haptic_state["intensity"]
            pulse_on = haptic_state["pulse_on"]
            pulse_off = haptic_state["pulse_off"]
            trial_active = haptic_state["trial_active"]

        if not running:
            all_motors_off()
            break

        if not trial_active or not channels or intensity == 0:
            all_motors_off()
            time.sleep(UPDATE_INTERVAL)
            continue

        for ch, drv in drivers.items():
            if drv:
                drv.realtime_value = intensity if ch in channels else 0

        time.sleep(pulse_on)

        all_motors_off()
        time.sleep(pulse_off)


# ===================== TRIAL CONTROL =====================

def run_distance_trial():
    print("\n[TRIAL] Place the object now. Motors OFF for 7 seconds.")

    with state_lock:
        haptic_state["trial_active"] = False
        haptic_state["channels"] = []
        haptic_state["intensity"] = 0

    all_motors_off()
    time.sleep(PLACEMENT_TIME)

    print("[TRIAL] Buzzing for 5 seconds.")

    with state_lock:
        haptic_state["trial_active"] = True

    time.sleep(BUZZ_TIME)

    print("[TRIAL] Buzz complete. Motors OFF.")

    with state_lock:
        haptic_state["trial_active"] = False
        haptic_state["channels"] = []
        haptic_state["intensity"] = 0

    all_motors_off()
    time.sleep(TRIAL_PAUSE_TIME)


# ===================== CLEANUP =====================

def cleanup():
    with state_lock:
        haptic_state["running"] = False

    all_motors_off()

    if picam2:
        try:
            picam2.stop()
        except Exception:
            pass

    print("\n[INFO] System stopped safely.")


def handle_exit(sig, frame):
    cleanup()
    sys.exit(0)


# ===================== HARDWARE INIT =====================

def init_motors():
    global drivers

    print("[INFO] Initializing I2C motors...")

    i2c = busio.I2C(board.SCL, board.SDA)
    tca = adafruit_tca9548a.TCA9548A(i2c)

    for ch in ALL_MOTORS_RAW:
        try:
            drv = DRV2605(tca[ch])
            drv.mode = MODE_REALTIME
            drv.realtime_value = 0
            drivers[ch] = drv
            available_channels.add(ch)
            print(f"[OK] Motor channel {ch} ready")
        except Exception as e:
            drivers[ch] = None
            print(f"[WARN] Motor channel {ch} not found: {e}")


def init_camera():
    global picam2

    print("[INFO] Initializing camera...")

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (CAM_W, CAM_H), "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()

    time.sleep(1)


# ===================== MAIN =====================

def main():
    global model, calibrated, calibration_height

    print("[INFO] Initializing system...")

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    init_motors()
    init_camera()

    model = YOLO(MODEL_PATH)

    threading.Thread(target=motor_loop, daemon=True).start()

    print("[INFO] System ready.")
    print("[INFO] Press 's' to calibrate object height at 5m.")
    print("[INFO] Press 't' to start a distance trial.")
    print("[INFO] Press 'q' to quit.")

    while True:
        frame = picam2.capture_array()
        now = time.time()

        results = model(frame, verbose=False)
        best, best_label = find_best_target(results)

        if best is not None and best_label is not None:
            x1, y1, x2, y2 = map(int, best.xyxy[0])
            height = y2 - y1
            conf = float(best.conf[0])

            height_buffer.append(height)
            avg_height = sum(height_buffer) / len(height_buffer)

            raw_distance = height_to_distance_m(avg_height)

            if raw_distance is not None:
                distance_buffer.append(raw_distance)
                avg_distance = sum(distance_buffer) / len(distance_buffer)

                track_state["distance_m"] = ema(
                    track_state["distance_m"],
                    avg_distance,
                    DIST_EMA_ALPHA
                )

            smooth_distance = track_state["distance_m"]

            intensity = distance_to_intensity(smooth_distance)
            pulse_on, pulse_off = distance_to_pulse(smooth_distance)

            with state_lock:
                haptic_state["channels"] = ALL_MOTORS_RAW
                haptic_state["intensity"] = intensity
                haptic_state["pulse_on"] = pulse_on
                haptic_state["pulse_off"] = pulse_off
                haptic_state["last_seen"] = now

            print(
                f"[DETECT] conf={conf:.2f} "
                f"height={height}px "
                f"dist={smooth_distance} "
                f"intensity={intensity} "
                f"trial_active={haptic_state['trial_active']}"
            )

            if SHOW_PREVIEW:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                text = f"{DISPLAY_NAMES.get(best_label, best_label)} {conf:.2f}"
                if smooth_distance is not None:
                    text += f" {smooth_distance:.2f}m"

                cv2.putText(
                    frame,
                    text,
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

        else:
            with state_lock:
                time_since_seen = now - haptic_state["last_seen"]

                if time_since_seen > STALE_TIMEOUT:
                    haptic_state["channels"] = []
                    haptic_state["intensity"] = 0

            print("[MISS] No detection. Motors remain off unless trial is active.")

        if SHOW_PREVIEW:
            cv2.imshow("Distance Haptic Trial", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):
                if best is not None and best_label is not None:
                    x1, y1, x2, y2 = map(int, best.xyxy[0])
                    calibration_height = y2 - y1
                    calibrated = True

                    height_buffer.clear()
                    distance_buffer.clear()
                    track_state["distance_m"] = None

                    print(
                        f"[CALIBRATED] height={calibration_height}px "
                        f"at {CALIBRATION_DISTANCE_M}m"
                    )
                else:
                    print("[WARN] Cannot calibrate. No target detected.")

            elif key == ord("t"):
                run_distance_trial()

            elif key == ord("q"):
                break

    cleanup()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()