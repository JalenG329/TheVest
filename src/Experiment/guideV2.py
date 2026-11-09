
# guide_v2.py
# ============================================================
# GUIDE V2: guidance built on what made demo.py work
#
#   1. SILENCE = CLEAR. No "is the path clear?" decision.
#   2. Only CLOSE readings count (under MAX_DEPTH, same as demo.py).
#      Far readings swing with the room, so they are ignored.
#   3. Each strip gets its own "closeness" (0 = nothing close,
#      1 = very close) Direction comes from comparing those:
#      steer AWAY from the side with more close stuff.
#   4. Graded cues: stronger when the decision is clear-cut,
#      faster pulses when the obstacle ahead is closer.
#
#   Motor meanings (same as the other guidance scripts):
#       6, 4  left column   go LEFT
#       0, 1  right column  go RIGHT
#       5, 3  back center   BLOCKED (pulses) / STOP (rapid)
#       7, 2  front center  unused: silence means clear
#
#   Optional YOLO: a person/chair straight ahead counts as an obstacle
#   even when depth misses it (depth reads people as farther than they are),
#   and STOPs when its box fills the frame.

# ============================================================

import os
import csv
import time
import signal
import threading
import traceback

import cv2
import numpy as np
import degirum as dg
from picamera2 import Picamera2

import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME


def _stop_on_signal(signum, frame):
    raise KeyboardInterrupt          # run the normal shutdown (motors off)


for _sig in (signal.SIGTERM, signal.SIGHUP):
    signal.signal(_sig, _stop_on_signal)


# ============================================================
# MOTORS (wearer's view, left -> right)
#   FRONT ROW: 6   7   2   0
#   BACK ROW:  4   5   3   1
# ============================================================

LEFT_MOTORS = [6, 4]
RIGHT_MOTORS = [0, 1]
STOP_MOTORS = [5, 3]
# broken / awaiting replacement; remove when fixed
DISABLED_MOTORS = [5]
NAV_CHANNELS = [ch for ch in LEFT_MOTORS + RIGHT_MOTORS + STOP_MOTORS
                if ch not in DISABLED_MOTORS]


# ============================================================
# SETTINGS
# ============================================================

MIN_DEPTH = 0.5               # closeness 1.0 at/under this
MAX_DEPTH = 2.5               # closeness 0 at/over this: ignored
AHEAD_DEPTH = 2.4             # your path reads closer than this -> start guiding
AHEAD_EXIT = 2.6              # ...and must read farther than this to go silent again
STOP_DEPTH = 1.25             # your path reads closer than this -> STOP
# (wall 1 m ~1.08-1.18, wall 2 m ~1.32-1.36)
# sides must differ by this much (closeness) to pick one
SIDE_DIFF = 0.15

USE_YOLO = True               # False = depth only
# person/chair box this tall (fraction of frame) = ahead
YOLO_NEAR_HEIGHT = 0.40
# ... this tall = STOP (check "h:" in the preview at 1 m)
YOLO_STOP_HEIGHT = 0.90

# Pulses
STRENGTH = 127                # clear-cut decision (127 = maximum)
STRENGTH_MIN = 127             # sides barely differ (weaker = "less sure")
PULSE_ON = 0.15               # seconds each pulse lasts
FAR_GAP, NEAR_GAP = 0.70, 0.10   # pause between pulses: just noticed -> almost STOP
STOP_ON, STOP_GAP = 0.15, 0.05   # STOP: rapid

# a new cue must repeat this many frames (STOP is instant)
CONFIRM_FRAMES = 3
SWITCH_MARGIN = 0.10          # keep steering the same way unless the other side
# is this much clearer

# Rarely changed
CAM_W, CAM_H = 640, 360
ROI_Y = (0.25, 0.80)          # ignore ceiling and the floor at your feet
SMOOTHING_ALPHA = 0.3         # lower = smoother (demo.py)
CENTER_STRIPS = (2, 3, 4)     # your walking path (~1 m wide at 2 m away)
LEFT_STRIPS, RIGHT_STRIPS = (0, 1, 2), (4, 5, 6)
YOLO_EVERY = 2                # run YOLO every Nth frame
YOLO_CONFIDENCE = 0.40
OBSTACLE_CLASSES = {"person", "chair", "bench", "couch", "backpack", "suitcase",
                    "dining table", "potted plant"}
CENTER_ZONE = (0.33, 0.67)    # box center in this part of the width = "ahead"
YOLO_SIDE_WEIGHT = 0.6        # how strongly an off-center box pushes you the other way
# with a YOLO obstacle ahead, any real side difference counts
YOLO_SIDE_DIFF = 0.02

HAPTIC_HZ = 100
CHECK_EVERY = 1.0             # seconds between driver health checks
REPORT_EVERY = 5.0
STAGGER = 0.02                # spread motor start-up current
SHOW_WINDOW = True            # camera + depth preview (False = no window)
PREVIEW_EVERY = 3
LOG = True

MODELS_DIR = "/home/rohan/degirum_wearable_device/models"
YOLO_DIR = "/home/rohan/haptic feedback vest final/models"


# ============================================================
# LOGGING
# ============================================================

class CsvLog:
    HEADER = ["time", "frame_ms", "L", "C",
              "R", "state", "intensity", "yolo_near"]

    def __init__(self, name):
        os.makedirs("logs", exist_ok=True)
        path = f"logs/{name}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.f = open(path, "w", newline="", buffering=1)
        self.w = csv.writer(self.f)
        self.w.writerow(self.HEADER)
        print(f"Logging to {path}")

    def row(self, *values):
        self.w.writerow([f"{v:.3f}" if isinstance(
            v, float) else v for v in values])

    def close(self):
        self.f.close()


# ============================================================
# HAPTICS: one self-healing thread pulses every motor
#   targets = {channel: (strength, on_seconds, off_seconds)}
# ============================================================

class Haptics:
    def __init__(self):
        self.tca = adafruit_tca9548a.TCA9548A(busio.I2C(board.SCL, board.SDA))
        self.motors = {ch: self._setup(ch) for ch in NAV_CHANNELS}
        self.targets = {}
        self.levels = {ch: 0 for ch in NAV_CHANNELS}
        self.active = {ch: False for ch in NAV_CHANNELS}
        self.on = {ch: False for ch in NAV_CHANNELS}
        self.t = {ch: 0.0 for ch in NAV_CHANNELS}
        self.errors = self.resets = 0
        self.recent_resets = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _setup(self, ch, quiet=False):
        try:
            drv = DRV2605(self.tca[ch])
            drv.mode = MODE_REALTIME
            drv.realtime_value = 0
            return drv
        except Exception as e:
            if not quiet:
                print(f"Motor {ch} unavailable: {e}")
            return None

    def _check(self):
        """Re-setup any driver that reset (it would ignore commands otherwise)."""
        for ch, drv in self.motors.items():
            if drv is None:
                continue
            try:
                mode = drv.mode
            except Exception:
                self.errors += 1
                continue
            if mode != MODE_REALTIME:
                fresh = self._setup(ch, quiet=True)
                if fresh:
                    self.motors[ch], self.levels[ch] = fresh, 0
                    self.resets += 1
                    count = self.recent_resets.get(ch, (0, 0))[0] + 1
                    self.recent_resets[ch] = (count, mode)

    def _value(self, ch, spec, now):
        """Where this motor should be right now, following its pulse rhythm."""
        if not spec or spec[0] <= 0:
            self.active[ch] = self.on[ch] = False
            return 0
        strength, on_t, off_t = spec
        if not self.active[ch]:
            self.active[ch], self.on[ch], self.t[ch] = True, True, now
        elif self.on[ch] and now - self.t[ch] >= on_t:
            self.on[ch], self.t[ch] = off_t <= 0, now
        elif not self.on[ch] and now - self.t[ch] >= off_t:
            self.on[ch], self.t[ch] = True, now
        return strength if self.on[ch] else 0

    def _run(self):
        period = 1.0 / HAPTIC_HZ
        next_check, reported, next_report = time.monotonic() + CHECK_EVERY, 0, 0.0
        while not self._stop.is_set():
            try:
                now = time.monotonic()
                targets = self.targets
                started = False
                for ch, drv in self.motors.items():
                    new = self._value(ch, targets.get(ch), now)
                    if drv is None or new == self.levels[ch]:
                        continue
                    if new and not self.levels[ch] and started:
                        time.sleep(STAGGER)
                    try:
                        drv.realtime_value = new
                        self.levels[ch] = new
                        started = started or bool(new)
                    except Exception:
                        self.errors += 1
                if now >= next_check:
                    self._check()
                    next_check = now + CHECK_EVERY
                    if self.recent_resets and now >= next_report:
                        print("WARNING: motor drivers reset and restored: " + ", ".join(
                            f"motor {c} {n}x (read {hex(m)})"
                            for c, (n, m) in sorted(self.recent_resets.items())))
                        self.recent_resets.clear()
                        next_report = now + REPORT_EVERY
                    if self.errors > reported:
                        print(
                            f"WARNING: {self.errors - reported} motor I2C errors")
                        reported = self.errors
            except Exception:
                traceback.print_exc()
                time.sleep(0.1)
            time.sleep(period)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
        for drv in self.motors.values():
            if drv:
                try:
                    drv.realtime_value = 0
                    drv._write_u8(0x01, 0x40)     # standby: outputs fully off
                except Exception:
                    pass
        print(
            f"Motor driver resets: {self.resets}   I2C errors: {self.errors}")


# ============================================================
# DEPTH -> CLOSENESS (the demo.py signal)
# ============================================================

def depth_processing(depth_result):
    out = depth_result._inference_results[0]
    q = out["quantization"]
    depth = (out["data"].astype(np.float32) - q["zero"][0]) * q["scale"][0]
    return cv2.GaussianBlur(depth.reshape(224, 224), (5, 5), 1.5)


def depth_in_7_segments(depth_map):
    h = depth_map.shape[0]
    band = depth_map[int(h * ROI_Y[0]):int(h * ROI_Y[1])]
    return np.array([np.median(s) for s in np.array_split(band, 7, axis=1)])


def closeness(d):
    """0 = nothing close (MAX_DEPTH or farther), 1 = very close (MIN_DEPTH)."""
    if not np.isfinite(d):
        return 0.0
    return float(np.clip((MAX_DEPTH - d) / (MAX_DEPTH - MIN_DEPTH), 0.0, 1.0))


# ============================================================
# GUIDANCE
# ============================================================

current_cue, pending_cue, pending_count = "CLEAR", None, 0


def decide(segments, obstacles):
    """Returns (raw cue, urgency 0-1, confidence 0-1, info for display)."""
    close = [closeness(d) for d in segments]
    # MEDIAN of the 3 middle strips: when you're slightly angled in a corridor,
    # one strip catches a side wall; the other two outvote it.
    ahead_depth = float(np.nanmedian(segments[list(CENTER_STRIPS)]))
    left = float(np.mean([close[i] for i in LEFT_STRIPS])
                 )      # how much close stuff
    right = float(np.mean([close[i] for i in RIGHT_STRIPS]))
    urgency = float(np.clip((MAX_DEPTH - ahead_depth) /
                    (MAX_DEPTH - STOP_DEPTH), 0, 1))

    # YOLO: something we recognize straight ahead
    ahead_objs = [o for o in obstacles if o["zone"] == "CENTER"]
    main_obj = max(ahead_objs, key=lambda o: o["height"], default=None)
    tallest = main_obj["height"] if main_obj else 0.0
    yolo_ahead = tallest >= YOLO_NEAR_HEIGHT
    if yolo_ahead:
        urgency = max(urgency, float(np.clip((tallest - YOLO_NEAR_HEIGHT)
                                             / (YOLO_STOP_HEIGHT - YOLO_NEAR_HEIGHT), 0, 1)))
    info = {"left": left, "right": right,
            "ahead": ahead_depth, "yolo": tallest}

    if ahead_depth <= STOP_DEPTH or tallest >= YOLO_STOP_HEIGHT:
        return "STOP", 1.0, 1.0, info
    clear_above = AHEAD_EXIT if current_cue != "CLEAR" else AHEAD_DEPTH
    if ahead_depth >= clear_above and not yolo_ahead:
        return "CLEAR", 0.0, 0.0, info                   # silence

    # > 0: left has more close stuff
    diff = left - right
    needed = SIDE_DIFF
    if yolo_ahead:
        # an object left of center pushes you right, and vice versa
        diff += (0.5 - main_obj.get("cx", 0.5)) * YOLO_SIDE_WEIGHT
        needed = YOLO_SIDE_DIFF
    confidence = float(np.clip(abs(diff) / 0.4, 0, 1))
    # keep going the same way...
    if current_cue in ("LEFT", "RIGHT"):
        favors = diff if current_cue == "RIGHT" else -diff   # > 0: still the better side
        if favors > -SWITCH_MARGIN and abs(diff) >= needed / 2:
            # ...unless the other is clearly better
            return current_cue, urgency, confidence, info
    if abs(diff) >= needed:
        return ("RIGHT" if diff > 0 else "LEFT"), urgency, confidence, info
    return "BLOCKED", urgency, confidence, info          # both sides similar


def stabilize(raw):
    """STOP is immediate; any other change must repeat CONFIRM_FRAMES times."""
    global current_cue, pending_cue, pending_count
    if raw == "STOP" or raw == current_cue:
        current_cue, pending_cue, pending_count = raw, None, 0
    else:
        pending_count = pending_count + 1 if raw == pending_cue else 1
        pending_cue = raw
        if pending_count >= CONFIRM_FRAMES:
            current_cue, pending_cue, pending_count = raw, None, 0
    return current_cue


def cue_targets(cue, urgency, confidence):
    """Motor pulse specs for a cue."""
    if cue == "CLEAR":
        return {}
    if cue == "STOP":
        motors, spec = STOP_MOTORS, (STRENGTH, STOP_ON, STOP_GAP)
    else:
        steps = round(urgency * 3) / 3                    # 4 distinct speeds
        gap = FAR_GAP + (NEAR_GAP - FAR_GAP) * steps
        strength = int(STRENGTH_MIN + (STRENGTH - STRENGTH_MIN) * confidence)
        if cue == "BLOCKED":
            strength = STRENGTH
        motors = {"LEFT": LEFT_MOTORS, "RIGHT": RIGHT_MOTORS}.get(
            cue, STOP_MOTORS)
        spec = (strength, PULSE_ON, gap)
    return {ch: spec for ch in motors if ch in NAV_CHANNELS}


# ============================================================
# YOLO
# ============================================================

def obstacles_from(result, fw, fh):
    found = []
    for det in result.results:
        label = (det.get("label") or "").lower()
        if det.get("score", 0) < YOLO_CONFIDENCE or label not in OBSTACLE_CLASSES \
                or det.get("bbox") is None:
            continue
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        ratio = (x1 + x2) / 2 / fw
        zone = "CENTER" if CENTER_ZONE[0] <= ratio <= CENTER_ZONE[1] else "SIDE"
        found.append({"label": label, "bbox": (x1, y1, x2, y2), "zone": zone,
                      "height": (y2 - y1) / fh, "cx": ratio})
    return found


# ============================================================
# PREVIEW: camera | depth (red = close, blue = far)
# ============================================================

def draw(frame, depth_map, segments, obstacles, cue, info, fps):
    h, w = frame.shape[:2]
    cam = frame.copy()
    close_map = np.clip((MAX_DEPTH - depth_map) /
                        (MAX_DEPTH - MIN_DEPTH), 0, 1)
    dep = cv2.resize(cv2.applyColorMap((close_map * 255).astype(np.uint8), cv2.COLORMAP_JET),
                     (w, h), interpolation=cv2.INTER_NEAREST)
    y1, y2 = int(h * ROI_Y[0]), int(h * ROI_Y[1])
    sw = w / 7
    for view in (cam, dep):
        cv2.line(view, (0, y1), (w, y1), (255, 255, 255), 1)
        cv2.line(view, (0, y2), (w, y2), (255, 255, 255), 1)
        for i in range(1, 7):
            cv2.line(view, (int(i * sw), y1),
                     (int(i * sw), y2), (255, 255, 255), 1)
        for i, d in enumerate(segments):
            color = (0, 255, 255) if closeness(d) > 0 else (255, 255, 255)
            cv2.putText(view, f"{d:.1f}", (int(i * sw) + 4, y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    for o in obstacles:
        bx1, by1, bx2, by2 = o["bbox"]
        color = (0, 0, 255) if o["zone"] == "CENTER" else (0, 255, 255)
        cv2.rectangle(cam, (bx1, by1), (bx2, by2), color, 2)
        cv2.putText(cam, f"{o['label']} h:{o['height']:.2f}", (bx1, max(15, by1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    arrow = {"LEFT": "<- LEFT", "RIGHT": "RIGHT ->", "BLOCKED": "BLOCKED",
             "STOP": "X STOP", "CLEAR": "(silent)"}[cue]
    cv2.putText(cam, f"{arrow}   FPS {fps:.1f}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 255, 255), 2)
    cv2.putText(cam, f"close L {info['left']:.2f}  R {info['right']:.2f}  ahead {info['ahead']:.2f}",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(dep, "DEPTH  red = close, blue = far", (10, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return np.hstack([cam, dep])


# ============================================================
# MAIN
# ============================================================

def main():
    camera = haptics = log = None
    try:
        print("Loading models...")
        depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1",
                                    "@local", MODELS_DIR)
        yolo = None
        if USE_YOLO:
            yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
                                 "@local", YOLO_DIR)
            yolo.input_numpy_colorspace = "BGR"    # Picamera2 RGB888 is stored B,G,R

        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(
            main={"size": (CAM_W, CAM_H), "format": "RGB888"}))
        camera.start()
        time.sleep(1.0)

        haptics = Haptics()
        log = CsvLog("guide_v2") if LOG else None
        print(f"\nGUIDE V2 | silent unless something is closer than {AHEAD_DEPTH} "
              f"| STOP <= {STOP_DEPTH} | YOLO {'ON' if yolo else 'OFF'} | Ctrl+C = quit\n")

        smooth, obstacles, last_cue = None, [], None
        n, frames, fps, t_fps = 0, 0, 0.0, time.monotonic()

        while True:
            t0 = time.monotonic()
            frame = camera.capture_array("main")
            fh, fw = frame.shape[:2]

            depth_map = depth_processing(depth_model.predict(frame))
            seg = depth_in_7_segments(depth_map)
            if smooth is None:
                smooth = seg
            else:
                blend = SMOOTHING_ALPHA * seg + (1 - SMOOTHING_ALPHA) * smooth
                smooth = np.where(~np.isfinite(seg), smooth,
                                  np.where(~np.isfinite(smooth), seg, blend))

            n += 1
            if yolo and n % YOLO_EVERY == 0:
                obstacles = obstacles_from(yolo.predict(frame), fw, fh)

            raw, urgency, confidence, info = decide(smooth, obstacles)
            cue = stabilize(raw)
            targets = cue_targets(cue, urgency, confidence)
            haptics.targets = targets

            if cue != last_cue:
                print(f"{cue:8s} | close L {info['left']:.2f} R {info['right']:.2f} "
                      f"| ahead {info['ahead']:.2f} | YOLO h {info['yolo']:.2f}")
                last_cue = cue
            if log:
                strength = next(iter(targets.values()))[0] if targets else 0
                log.row(time.time(), (time.monotonic() - t0) * 1000, info["left"],
                        info["ahead"], info["right"], cue, strength,
                        sum(o["zone"] == "CENTER" for o in obstacles))

            frames += 1
            if time.monotonic() - t_fps >= 1.0:
                fps = frames / (time.monotonic() - t_fps)
                frames, t_fps = 0, time.monotonic()

            if SHOW_WINDOW and n % PREVIEW_EVERY == 0:
                cv2.imshow("Guide V2: camera | depth",
                           draw(frame, depth_map, smooth, obstacles, cue, info, fps))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception:
        traceback.print_exc()
    finally:
        if haptics:
            haptics.close()
        if camera:
            try:
                camera.stop()
            except Exception:
                pass
        if log:
            log.close()
        cv2.destroyAllWindows()
        print("System stopped.")


if __name__ == "__main__":
    main()
