# ============================================================
# DISTANCE-ONLY HAPTIC JACKET
# MAX DANGER INTENSITY VERSION
# ANY OBJECT - NO CALIBRATION
#
# DISTANCE ZONES:
# FAR      > 3 meters
# MEDIUM   3 - 2 meters
# CLOSE    2 - 1 meters
# DANGER   < 0.5 meters
# ============================================================

import time
import threading
import atexit
import signal
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO
from picamera2 import Picamera2

import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME


# ===================== CONFIG =====================

MODEL_PATH = "yolo11n.pt"

CAM_W = 640
CAM_H = 480

CONF_THRESHOLD = 0.35
MIN_BBOX_HEIGHT = 20
MIN_BBOX_WIDTH = 10

MAX_DISTANCE_M = 4.0
DANGER_DISTANCE_M = 0.5

DIST_HISTORY_SIZE = 7
STALE_TIMEOUT = 0.30

SHOW_PREVIEW = True


# ===================== MOTOR LAYOUT =====================

DISTANCE_WARNING_MOTORS = [0, 2, 7, 6, 4, 5, 3, 1]
DANGER_MOTORS = [7, 6, 1, 3, 5, 4, 0, 2]


# ===================== GLOBAL =====================

drivers = {}
available_channels = set()

picam2 = None
model = None

distance_history = deque(maxlen=DIST_HISTORY_SIZE)

current_channels = []
current_intensity = 0
current_pulse_on = 0.1
current_pulse_off = 0.5
current_zone = "OFF"

last_detection_time = 0
running = True
state_lock = threading.Lock()


# ===================== SAFETY =====================

def all_off():
    for drv in drivers.values():
        if drv:
            drv.realtime_value = 0


def shutdown():
    global running, picam2

    running = False
    all_off()

    try:
        if picam2:
            picam2.stop()
    except:
        pass

    cv2.destroyAllWindows()
    print("[EXIT] Motors OFF")


atexit.register(shutdown)
signal.signal(signal.SIGINT, lambda a, b: shutdown())
signal.signal(signal.SIGTERM, lambda a, b: shutdown())


# ===================== MOTOR SETUP =====================

def init_motors():
    global drivers, available_channels

    i2c = busio.I2C(board.SCL, board.SDA)
    mux = adafruit_tca9548a.TCA9548A(i2c)

    for i in range(8):
        try:
            drv = DRV2605(mux[i])
            drv.mode = MODE_REALTIME
            drv.realtime_value = 0
            drivers[i] = drv
            available_channels.add(i)
            print(f"[OK] Motor {i}")
        except Exception as e:
            drivers[i] = None
            print(f"[WARN] Motor {i} not found: {e}")

    return len(available_channels) > 0


# ===================== CAMERA =====================

def init_camera():
    global picam2

    picam2 = Picamera2()

    config = picam2.create_preview_configuration(
        main={"size": (CAM_W, CAM_H), "format": "RGB888"}
    )

    picam2.configure(config)
    picam2.start()

    time.sleep(1)


# ===================== DISTANCE =====================

def get_distance(area):

    ratio = area / float(CAM_W * CAM_H)

    if ratio >= 0.40:
        return 0.4

    elif ratio >= 0.32:
        return 0.5

    elif ratio >= 0.25:
        return 0.75

    elif ratio >= 0.18:
        return 1.0

    elif ratio >= 0.12:
        return 1.5

    elif ratio >= 0.08:
        return 2.0

    elif ratio >= 0.05:
        return 2.5

    elif ratio >= 0.03:
        return 3.0

    elif ratio >= 0.02:
        return 3.5

    elif ratio >= 0.012:
        return 4.0

    else:
        return None


def smooth_distance(d):

    if d is None:
        return None

    distance_history.append(d)

    return float(np.median(distance_history))


# ===================== DISTANCE ZONES =====================

def get_distance_zone(d):

    if d is None:
        return "OFF"

    if d <= 0.5:
        return "DANGER"

    elif d <= 2.0:
        return "CLOSE"

    elif d <= 3.0:
        return "MEDIUM"

    elif d <= MAX_DISTANCE_M:
        return "FAR"

    return "OFF"


# ===================== INTENSITY =====================

def distance_to_intensity(d):

    zone = get_distance_zone(d)

    if zone == "DANGER":
        return 127

    elif zone == "CLOSE":
        return 118

    elif zone == "MEDIUM":
        return 78

    elif zone == "FAR":
        return 35

    else:
        return 0


# ===================== RHYTHM =====================

def distance_to_pulse(d):

    zone = get_distance_zone(d)

    # EXTREME DIFFERENCES

    if zone == "DANGER":
        return 0.35, 0.002

    elif zone == "CLOSE":
        return 0.18, 0.035

    elif zone == "MEDIUM":
        return 0.10, 0.22

    elif zone == "FAR":
        return 0.055, 0.65

    else:
        return 0.05, 0.90


# ===================== MOTOR CHOICE =====================

def choose_motors(d):

    zone = get_distance_zone(d)

    if zone == "OFF":
        return [], "off"

    if zone == "DANGER":
        return DANGER_MOTORS, "danger"

    return DISTANCE_WARNING_MOTORS, "distance"


# ===================== DETECTION =====================

def get_best(results):

    best = None
    best_score = -1

    for r in results:

        for box in r.boxes:

            conf = float(box.conf[0])

            if conf < CONF_THRESHOLD:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            w = x2 - x1
            h = y2 - y1

            if w < MIN_BBOX_WIDTH or h < MIN_BBOX_HEIGHT:
                continue

            area = w * h
            score = area * conf

            if score > best_score:
                best_score = score
                best = (x1, y1, x2, y2, area, conf)

    return best


# ===================== MOTOR LOOP =====================

def motor_loop():

    global current_channels
    global current_intensity
    global current_pulse_on
    global current_pulse_off
    global current_zone

    while running:

        with state_lock:

            ch = list(current_channels)

            intensity = current_intensity
            on = current_pulse_on
            off = current_pulse_off
            zone = current_zone

            stale = time.time() - last_detection_time > STALE_TIMEOUT

        if stale or not ch or intensity == 0:
            all_off()
            time.sleep(0.01)
            continue


        # ====================================================
        # DANGER MODE
        # MAXIMUM POSSIBLE FEELING
        # ====================================================

        if zone == "DANGER":

            # FIRST BLAST
            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = 127 if i in ch else 0

            time.sleep(0.30)

            all_off()
            time.sleep(0.008)

            # SECOND BLAST
            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = 127 if i in ch else 0

            time.sleep(0.22)

            all_off()
            time.sleep(0.008)

            # THIRD BLAST
            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = 120 if i in ch else 0

            time.sleep(0.16)

            all_off()
            time.sleep(0.01)

            continue


        # ====================================================
        # CLOSE
        # STRONG DOUBLE HEARTBEAT
        # ====================================================

        if zone == "CLOSE":

            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = intensity if i in ch else 0

            time.sleep(on)

            all_off()
            time.sleep(0.045)

            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = int(intensity * 0.70) if i in ch else 0

            time.sleep(on * 0.65)

            all_off()
            time.sleep(off)

            continue


        # ====================================================
        # MEDIUM
        # ====================================================

        if zone == "MEDIUM":

            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = intensity if i in ch else 0

            time.sleep(on)

            all_off()
            time.sleep(off)

            continue


        # ====================================================
        # FAR
        # ====================================================

        if zone == "FAR":

            for i, drv in drivers.items():
                if drv:
                    drv.realtime_value = intensity if i in ch else 0

            time.sleep(on)

            all_off()
            time.sleep(off)

            continue


# ===================== DISPLAY =====================

def draw_display(display, best, d, zone, intensity):

    if best is not None:

        x1, y1, x2, y2, area, conf = best

        ratio = area / float(CAM_W * CAM_H)

        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

        text1 = f"ZONE: {zone}"
        text2 = f"DIST: {d} m | INTENSITY: {intensity}"
        text3 = f"RATIO: {ratio:.3f} | CONF: {conf:.2f}"

        cv2.putText(display, text1, (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)

        cv2.putText(display, text2, (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

        cv2.putText(display, text3, (20, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    else:

        cv2.putText(display, "NO OBJECT DETECTED", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

    cv2.putText(display, "ESC = quit", (20, CAM_H - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)


# ===================== MAIN =====================

def main():

    global model
    global current_channels
    global current_intensity
    global current_pulse_on
    global current_pulse_off
    global current_zone
    global last_detection_time

    if not init_motors():
        print("[ERROR] No motors detected.")
        return

    init_camera()

    model = YOLO(MODEL_PATH)

    threading.Thread(target=motor_loop, daemon=True).start()

    print("[READY] MAX DANGER INTENSITY SYSTEM RUNNING")

    while running:

        frame = picam2.capture_array()
        display = frame.copy()

        results = model(frame, verbose=False)

        best = get_best(results)

        if best is None:

            with state_lock:

                current_channels = []
                current_intensity = 0
                current_pulse_on = 0.05
                current_pulse_off = 0.90
                current_zone = "OFF"

            all_off()

            d = None
            zone = "OFF"
            intensity = 0

        else:

            x1, y1, x2, y2, area, conf = best

            raw_distance = get_distance(area)

            d = smooth_distance(raw_distance)

            zone = get_distance_zone(d)

            motors, _ = choose_motors(d)

            intensity = distance_to_intensity(d)

            pulse_on, pulse_off = distance_to_pulse(d)

            with state_lock:

                current_channels = motors
                current_intensity = intensity
                current_pulse_on = pulse_on
                current_pulse_off = pulse_off
                current_zone = zone

                last_detection_time = time.time()

            print(f"[DIST] zone={zone} distance={d}m intensity={intensity}")

        if SHOW_PREVIEW:

            draw_display(display, best, d, zone, intensity)

            cv2.imshow(
                "Heartbeat Distance",
                cv2.cvtColor(display, cv2.COLOR_RGB2BGR)
            )

            if cv2.waitKey(1) == 27:
                break

    shutdown()


if __name__ == "__main__":
    main()