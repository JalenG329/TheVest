# haptic_v6_5zone_stop_nav.py
# ---------------------------------------------------------
# 5-Zone Haptic Navigation System
# - 4 upper zones (YOLO + Depth fusion)
# - 1 bottom zone (Depth-only, 20% height)
# - STOP sign used as navigation beacon (continuous exponential cycles)
# - Person/Object override STOP if closer
# - MODE_REALTIME haptics with perceptually equal intensity levels
# - Missed-frame tolerant (2-frame hysteresis)
# - Full motor debug prints

import degirum as dg
import degirum_tools
from picamera2 import Picamera2
import cv2
import numpy as np
import time
import math
import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME
from collections import deque

# ===================== CONFIG =====================
CAM_W, CAM_H = 960, 540
DEPTH_SIZE = 224

NUM_ZONES = 5
BOTTOM_ZONE_RATIO = 0.20   # bottom 20% height

MAX_DEPTH = 4.0
MIN_DEPTH = 0.5

UPDATE_INTERVAL = 0.08
MIN_UPDATE_STEP = 3

# Hysteresis
CONFIRM_FRAMES = 2
EMPTY_FRAMES = 2

# Exponential cycle timing
CYCLE_PERIOD = 1.4
CYCLE_DROP = 25   # drop from stage intensity

# STOP navigation thresholds (meters)
STOP_DIST_LEVELS = [
    (3.0, 60),    # far
    (2.0, 85),    # medium
    (1.2, 110),   # near
    (0.5, 127)    # very near
]

# ===================== CAMERA =====================
camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (CAM_W, CAM_H), "format": "RGB888"}))
camera.start()
time.sleep(1.2)

# ===================== MODELS =====================
depth_model = dg.load_model(
    "fastdepth--224x224_quant_hailort_hailo8_1",
    "@local",
    "/home/rohan/degirum_wearable_device/models"
)

det_model = dg.load_model(
    "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    "@local",
    "/home/rohan/degirum_wearable_device/models",
    overlay_show_labels=False,
    overlay_show_probabilities=False
)

tracker = degirum_tools.ObjectTracker(
    track_thresh=0.4,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=False
)

# ===================== I2C + DRV =====================
i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

# Motor order (IMPORTANT)
# 0: far left (ch3)
# 1: slight left (ch5)
# 2: slight right (ch7)
# 3: far right (ch0)
# 4: bottom (ch1)
DRV_CHANNEL_MAP = [3, 5, 7, 0, 1]

MOTOR_LABELS = {
    0: "FAR LEFT (ch 3)",
    1: "SLIGHT LEFT (ch 5)",
    2: "SLIGHT RIGHT (ch 7)",
    3: "FAR RIGHT (ch 0)",
    4: "BOTTOM (ch 1)"
}

drvs = []
for ch in DRV_CHANNEL_MAP:
    time.sleep(0.12)
    d = DRV2605(mux[ch])
    d.mode = MODE_REALTIME
    d.realtime_value = 0
    drvs.append(d)

# ===================== HELPERS =====================


def depth_raw(depth_result):
    raw = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    return ((raw.astype(np.float32) - zero) * scale).reshape((DEPTH_SIZE, DEPTH_SIZE))


def get_stop_intensity(dist):
    for d, level in STOP_DIST_LEVELS:
        if dist > d:
            return level
    return 127


def exponential_cycle(stage_intensity, t):
    start = max(0, stage_intensity - CYCLE_DROP)
    phase = (t % CYCLE_PERIOD) / CYCLE_PERIOD
    val = start * math.exp(phase * math.log(stage_intensity / start))
    return int(min(stage_intensity, val))


# ===================== STATE =====================
semantic_hist = [deque(maxlen=CONFIRM_FRAMES) for _ in range(NUM_ZONES)]
dist_hist = [deque(maxlen=CONFIRM_FRAMES) for _ in range(NUM_ZONES)]

pattern_state = {
    i: {"mode": "none", "last": 0}
    for i in range(NUM_ZONES)
}

last_update = 0.0

# ===================== MAIN LOOP =====================
print("System running. Press 'q' to exit.")

with degirum_tools.Display("Haptic v6 5-Zone Navigation") as disp:
    while True:
        frame = camera.capture_array("main")

        # ---------- YOLO ----------
        det_res = det_model.predict(frame)
        try:
            tracker.analyze(det_res)
        except:
            pass
        img = tracker.annotate(det_res, det_res.image_overlay)

        # ---------- DEPTH ----------
        depth_map = depth_raw(depth_model.predict(frame))
        h_raw, w_raw = depth_map.shape

        bottom_cut = int(h_raw * (1 - BOTTOM_ZONE_RATIO))

        zone_depths = [None]*NUM_ZONES

        # Upper 4 zones (columns)
        col_w = w_raw // 4
        for i in range(4):
            seg = depth_map[:bottom_cut, i*col_w:(i+1)*col_w]
            zone_depths[i] = float(np.nanmedian(seg))

        # Bottom zone (full width)
        zone_depths[4] = float(np.nanmedian(depth_map[bottom_cut:, :]))

        # ---------- DETECTION FUSION ----------
        candidates = {}

        for det in det_res.results:
            label = det["label"].lower()
            x1, y1, x2, y2 = det["bbox"]
            cx = (x1 + x2) / 2

            zone = min(3, int(cx / (CAM_W / 4)))

            depth_val = zone_depths[zone]
            candidates[zone] = (label, depth_val)

        # Bottom zone depth-only
        if zone_depths[4] < MAX_DEPTH:
            candidates[4] = ("object", zone_depths[4])

        # ---------- TEMPORAL UPDATE ----------
        for i in range(NUM_ZONES):
            if i in candidates:
                semantic, dist = candidates[i]
                semantic_hist[i].append(semantic)
                dist_hist[i].append(dist)
            else:
                semantic_hist[i].append(None)
                dist_hist[i].append(None)

        # ---------- HAPTIC COMPUTE ----------
        desired = [0]*NUM_ZONES
        now = time.time()

        for i in range(NUM_ZONES):
            sems = list(semantic_hist[i])
            dists = list(dist_hist[i])

            # Person priority
            if sems[-1] == "person":
                pattern_state[i]["mode"] = "person"
                desired[i] = 110
                continue

            # STOP navigation
            if "stop sign" in sems:
                dist = next((d for d in reversed(dists) if d), None)
                stage = get_stop_intensity(dist if dist else 2.5)
                pattern_state[i]["mode"] = "stop"
                desired[i] = exponential_cycle(stage, now)
                continue

            # Object
            if sems.count("object") >= CONFIRM_FRAMES:
                pattern_state[i]["mode"] = "object"
                desired[i] = 80
                continue

            # Empty
            if sems.count(None) >= EMPTY_FRAMES:
                pattern_state[i]["mode"] = "none"
                desired[i] = 0

        # ---------- MOTOR WRITE ----------
        if now - last_update > UPDATE_INTERVAL:
            for i, val in enumerate(desired):
                last = pattern_state[i]["last"]
                if abs(val - last) >= MIN_UPDATE_STEP:
                    drvs[i].realtime_value = int(val)
                    pattern_state[i]["last"] = int(val)

                    if val > 0:
                        print(f"[HAPTIC] {MOTOR_LABELS[i]} | "
                              f"Mode: {pattern_state[i]['mode']} | Intensity: {val}")
                    else:
                        print(f"[HAPTIC] {MOTOR_LABELS[i]} | OFF")

            last_update = now

        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
