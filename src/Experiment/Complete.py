# haptic_experiment.py
# ---------------------------------------------------------
# Haptic guidance experiment script
# Modes:
#   direction = direction only
#   distance  = distance only
#   combined  = direction + distance
#
# Camera preview is ON by default.
# Use --no-preview to disable it.
# ---------------------------------------------------------

import time
import threading
import argparse
import atexit
import signal
import sys
from collections import deque

import cv2
from ultralytics import YOLO
from picamera2 import Picamera2

import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME


CAM_W = 640
CAM_H = 480

ALL_MOTORS_RAW = [0, 1, 2, 3, 4, 5, 6, 7]

MOVE_LEFT_RAW = [4, 0, 2]
MOVE_RIGHT_RAW = [1, 7, 6]
FRONT_WARNING_RAW = ALL_MOTORS_RAW
DANGER_OVERRIDE_RAW = ALL_MOTORS_RAW

LEFT_ZONE = 0.30
RIGHT_ZONE = 0.70

INTENSITY_LEVELS = {
    1: 45,
    2: 65,
    3: 85,
    4: 105,
    5: 127,
}

drivers = {}
available_channels = set()

picam2 = None
model = None
args = None

calibrated = False
calibration_height = None

height_buffer = deque(maxlen=6)
distance_buffer = deque(maxlen=5)

state_lock = threading.Lock()

haptic_state = {
    "channels": [],
    "intensity": 0,
    "pulse_on": 0.18,
    "pulse_off": 0.25,
    "mode": "clear",
    "last_seen": 0.0,
    "running": True,
}

track_state = {
    "x_center": None,
    "distance_m": None,
    "mode": "clear",
    "last_mode_change": 0.0,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stable haptic object guidance experiment script"
    )

    parser.add_argument(
        "--mode",
        choices=["direction", "distance", "combined"],
        default="combined",
        help="Experiment mode"
    )

    parser.add_argument("--target", default="chair", help="YOLO object class to detect")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLO model path")
    parser.add_argument("--conf", type=float, default=0.25, help="Detection confidence threshold")
    parser.add_argument("--cal-distance", type=float, default=5.0, help="Calibration distance in meters")
    parser.add_argument("--danger", type=float, default=1.0, help="Danger distance in meters")
    parser.add_argument("--min-distance", type=float, default=0.5, help="Minimum clamped distance")
    parser.add_argument("--max-distance", type=float, default=4.0, help="Maximum clamped distance")
    parser.add_argument("--stale", type=float, default=0.50, help="Hold last haptic signal after missed detection")
    parser.add_argument("--mode-hold", type=float, default=0.20, help="Minimum time before switching haptic modes")
    parser.add_argument("--min-box-height", type=int, default=25, help="Ignore detections below this box height")
    parser.add_argument("--x-alpha", type=float, default=0.30, help="Smoothing for horizontal position")
    parser.add_argument("--dist-alpha", type=float, default=0.30, help="Smoothing for distance")

    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable camera preview window"
    )

    parser.add_argument(
        "--no-motors",
        action="store_true",
        help="Debug without motor hardware"
    )

    return parser.parse_args()


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


def height_to_distance_m(height_px):
    if not calibrated or calibration_height is None:
        return None

    if height_px <= 0:
        return None

    distance = (args.cal_distance * calibration_height) / float(height_px)
    return clamp(distance, args.min_distance, args.max_distance)


def get_distance_level(distance_m):
    if distance_m is None:
        return 3

    if distance_m <= 1.0:
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

    if level == 1:
        return 0.12, 0.36
    elif level == 2:
        return 0.14, 0.28
    elif level == 3:
        return 0.16, 0.22
    elif level == 4:
        return 0.18, 0.16
    else:
        return 0.22, 0.08


def get_camera_zone(x_center):
    x_norm = x_center / CAM_W

    if x_norm < LEFT_ZONE:
        return "left"
    elif x_norm > RIGHT_ZONE:
        return "right"
    return "center"


def apply_mode_hold(new_mode, now):
    old_mode = track_state["mode"]

    if new_mode == "danger":
        track_state["mode"] = new_mode
        track_state["last_mode_change"] = now
        return new_mode

    if old_mode == "clear":
        track_state["mode"] = new_mode
        track_state["last_mode_change"] = now
        return new_mode

    if new_mode != old_mode:
        if now - track_state["last_mode_change"] < args.mode_hold:
            return old_mode

        track_state["mode"] = new_mode
        track_state["last_mode_change"] = now

    return track_state["mode"]


def choose_haptics(zone, distance_m):
    intensity = distance_to_intensity(distance_m)
    pulse_on, pulse_off = distance_to_pulse(distance_m)

    danger = distance_m is not None and distance_m <= args.danger

    if args.mode == "direction":
        intensity = 100
        pulse_on = 0.18
        pulse_off = 0.20

        if zone == "left":
            return MOVE_RIGHT_RAW, intensity, pulse_on, pulse_off, "move_right"
        elif zone == "right":
            return MOVE_LEFT_RAW, intensity, pulse_on, pulse_off, "move_left"
        else:
            return FRONT_WARNING_RAW, intensity, pulse_on, pulse_off, "front"

    elif args.mode == "distance":
        return FRONT_WARNING_RAW, intensity, pulse_on, pulse_off, "distance"

    else:
        if danger:
            return DANGER_OVERRIDE_RAW, 127, 0.25, 0.05, "danger"

        if zone == "left":
            return MOVE_RIGHT_RAW, intensity, pulse_on, pulse_off, "move_right"
        elif zone == "right":
            return MOVE_LEFT_RAW, intensity, pulse_on, pulse_off, "move_left"
        else:
            return FRONT_WARNING_RAW, intensity, pulse_on, pulse_off, "front"


def find_best_target(results):
    best_box = None
    best_score = 0

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]

            if label != args.target:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            height = y2 - y1

            if conf < args.conf:
                continue

            if height < args.min_box_height:
                continue

            score = conf * height

            if score > best_score:
                best_score = score
                best_box = box

    return best_box


def motor_loop():
    while True:
        with state_lock:
            running = haptic_state["running"]
            channels = list(haptic_state["channels"])
            intensity = haptic_state["intensity"]
            pulse_on = haptic_state["pulse_on"]
            pulse_off = haptic_state["pulse_off"]

        if not running:
            all_motors_off()
            break

        if not channels or intensity <= 0:
            all_motors_off()
            time.sleep(0.01)
            continue

        if not args.no_motors:
            for ch, drv in drivers.items():
                if drv:
                    drv.realtime_value = intensity if ch in channels else 0

        time.sleep(pulse_on)

        if not args.no_motors:
            all_motors_off()

        time.sleep(pulse_off)


def init_motors():
    if args.no_motors:
        print("[INFO] Motor hardware disabled.")
        return

    print("[INFO] Initializing motors...")

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
            print(f"[WARN] Motor channel {ch} failed: {e}")


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


def cleanup():
    with state_lock:
        haptic_state["running"] = False

    all_motors_off()

    if picam2:
        try:
            picam2.stop()
        except Exception:
            pass

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    print("\n[INFO] System stopped safely.")


def handle_exit(sig, frame):
    cleanup()
    sys.exit(0)


def main():
    global args, model, calibrated, calibration_height

    args = parse_args()

    print("[INFO] Starting haptic experiment.")
    print(f"[INFO] Mode: {args.mode}")
    print(f"[INFO] Target: {args.target}")
    print(f"[INFO] Confidence threshold: {args.conf}")
    print(f"[INFO] Stale hold: {args.stale}s")

    if not args.no_preview:
        print("[INFO] Preview enabled.")
        print("[INFO] Press 's' in preview window to calibrate.")
        print("[INFO] Press 'q' in preview window to quit.")
    else:
        print("[INFO] Preview disabled.")

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    init_motors()
    init_camera()

    print("[INFO] Loading YOLO model...")
    model = YOLO(args.model)

    threading.Thread(target=motor_loop, daemon=True).start()

    print("[INFO] Ready.")
    print("[INFO] Press CTRL+C to stop.")

    while True:
        frame = picam2.capture_array()
        now = time.time()

        results = model(frame, verbose=False)
        best = find_best_target(results)

        if best is not None:
            x1, y1, x2, y2 = map(int, best.xyxy[0])
            height = y2 - y1
            conf = float(best.conf[0])

            height_buffer.append(height)
            avg_height = sum(height_buffer) / len(height_buffer)

            raw_distance = height_to_distance_m(avg_height)

            if raw_distance is not None:
                distance_buffer.append(raw_distance)
                avg_distance = sum(distance_buffer) / len(distance_buffer)
            else:
                avg_distance = None

            x_center = (x1 + x2) / 2

            track_state["x_center"] = ema(
                track_state["x_center"],
                x_center,
                args.x_alpha
            )

            if avg_distance is not None:
                track_state["distance_m"] = ema(
                    track_state["distance_m"],
                    avg_distance,
                    args.dist_alpha
                )

            smooth_x = track_state["x_center"]
            smooth_distance = track_state["distance_m"]

            zone = get_camera_zone(smooth_x)

            channels, intensity, pulse_on, pulse_off, new_mode = choose_haptics(
                zone,
                smooth_distance
            )

            stable_mode = apply_mode_hold(new_mode, now)

            if args.mode == "combined":
                if stable_mode == "danger":
                    channels = DANGER_OVERRIDE_RAW
                    intensity = 127
                    pulse_on = 0.25
                    pulse_off = 0.05
                elif stable_mode == "move_right":
                    channels = MOVE_RIGHT_RAW
                elif stable_mode == "move_left":
                    channels = MOVE_LEFT_RAW
                elif stable_mode == "front":
                    channels = FRONT_WARNING_RAW

            elif args.mode == "direction":
                if stable_mode == "move_right":
                    channels = MOVE_RIGHT_RAW
                elif stable_mode == "move_left":
                    channels = MOVE_LEFT_RAW
                else:
                    channels = FRONT_WARNING_RAW

            elif args.mode == "distance":
                channels = FRONT_WARNING_RAW

            with state_lock:
                haptic_state["channels"] = channels
                haptic_state["intensity"] = intensity
                haptic_state["pulse_on"] = pulse_on
                haptic_state["pulse_off"] = pulse_off
                haptic_state["mode"] = stable_mode
                haptic_state["last_seen"] = now

            dist_text = "uncalibrated"
            if smooth_distance is not None:
                dist_text = f"{smooth_distance:.2f}m"

            print(
                f"[DETECT] mode={args.mode} "
                f"target={args.target} "
                f"conf={conf:.2f} "
                f"zone={zone} "
                f"dist={dist_text} "
                f"haptic={stable_mode} "
                f"intensity={intensity}"
            )

            if not args.no_preview:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                text = f"{args.target} {conf:.2f} {dist_text} {stable_mode}"
                cv2.putText(
                    frame,
                    text,
                    (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

        else:
            with state_lock:
                time_since_seen = now - haptic_state["last_seen"]

                if time_since_seen > args.stale:
                    haptic_state["channels"] = []
                    haptic_state["intensity"] = 0
                    haptic_state["mode"] = "clear"
                    track_state["mode"] = "clear"

            print("[MISS] No detection. Holding briefly before clearing.")

        if not args.no_preview:
            cv2.imshow("Haptic Experiment", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):
                if best is not None:
                    x1, y1, x2, y2 = map(int, best.xyxy[0])
                    calibration_height = y2 - y1
                    calibrated = True

                    height_buffer.clear()
                    distance_buffer.clear()
                    track_state["distance_m"] = None

                    print(
                        f"[CALIBRATED] {args.target} height="
                        f"{calibration_height}px at {args.cal_distance}m"
                    )
                else:
                    print("[WARN] Cannot calibrate. No target detected.")

            elif key == ord("q"):
                break

    cleanup()


if __name__ == "__main__":
    main()