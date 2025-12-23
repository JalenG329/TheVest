# haptic_v6_5zone_merged.py
# -------------------------------------------------------------
# Based on v5 logic
# NEW:
# - 5 zones total
#   Zones 0–3: upper 80% split into 4 vertical directions
#   Zone 4: bottom 20% horizontal band (near-field obstacles)

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

# ------------------- CONFIG -------------------
CAM_W, CAM_H = 960, 540
DEPTH_SIZE = 224

NUM_ZONES = 5
BOTTOM_RATIO = 0.20
BOTTOM_Y_START = int(CAM_H * (1 - BOTTOM_RATIO))

KNOWN_DISTANCE = 2.5
KNOWN_WIDTH = 0.4

UPDATE_INTERVAL = 0.08
MIN_UPDATE_STEP = 3
MAX_DEPTH = 4.0
MIN_DEPTH = 0.5
PERCEPTUAL_EXP = 0.6

# Heartbeat params
HB_P1 = 0.12
HB_G = 0.08
HB_P2 = 0.12
HB_BASE_REST = 0.6

# Hysteresis
OBJ_CONFIRM_FRAMES = 2
EMPTY_CONFIRM_FRAMES = 2

# ------------------- CAMERA -------------------
camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (CAM_W, CAM_H), "format": "RGB888"}))
camera.start()
time.sleep(1.2)

# ------------------- MODELS -------------------
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

# ------------------- I2C + DRV -------------------
i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

drv_channels = [mux[i] for i in [1, 3, 5, 7, 0]]  # 5 motors only
drvs = []

for ch in drv_channels:
    try:
        time.sleep(0.1)
        d = DRV2605(ch)
        d.mode = MODE_REALTIME
        d.realtime_value = 0
        drvs.append(d)
    except Exception as e:
        print(f"DRV init failed: {e}")

NUM_MOTORS = len(drvs)

# ------------------- HELPERS -------------------


def depth_raw_to_224(depth_result):
    raw = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    return ((raw.astype(np.float32) - zero) * scale).reshape((DEPTH_SIZE, DEPTH_SIZE))


def perceptual_map(depth_value):
    if depth_value is None or np.isnan(depth_value):
        return 0
    if depth_value >= MAX_DEPTH:
        return 0
    if depth_value <= MIN_DEPTH:
        return 127
    norm = 1.0 - (depth_value - MIN_DEPTH) / (MAX_DEPTH - MIN_DEPTH)
    return int(max(0, min(127, round((norm ** PERCEPTUAL_EXP) * 127))))


def resolve_zone(cx, cy):
    if cy >= BOTTOM_Y_START:
        return 4
    col_w = CAM_W / 4
    return int(min(3, max(0, cx // col_w)))


def depth_to_zones(depth_raw):
    h, w = depth_raw.shape
    zones = [None] * 5

    # Bottom zone
    y0 = int(h * (1 - BOTTOM_RATIO))
    zones[4] = float(np.nanmedian(depth_raw[y0:h, :]))

    # Upper zones
    col_w = w // 4
    for i in range(4):
        x0 = i * col_w
        x1 = (i + 1) * col_w if i < 3 else w
        zones[i] = float(np.nanmedian(depth_raw[:y0, x0:x1]))

    return zones


# ------------------- STATE -------------------
last_semantic = [deque(maxlen=2) for _ in range(NUM_MOTORS)]
last_dist = [deque(maxlen=2) for _ in range(NUM_MOTORS)]
pattern_state = {i: {"mode": "none", "hb_start": 0.0, "last_value": 0}
                 for i in range(NUM_MOTORS)}

last_update = 0.0

# ------------------- CALIBRATION -------------------
print("Calibrating...")
time.sleep(1.2)
ref = camera.capture_array("main")
res = det_model.predict(ref)
FOCAL_LENGTH = None

for det in res.results:
    if det["label"].lower() == "person":
        x1, _, x2, _ = det["bbox"]
        FOCAL_LENGTH = (x2 - x1) * KNOWN_DISTANCE / KNOWN_WIDTH
        break

# ------------------- MAIN LOOP -------------------
print("Running v6 (5-Zone)...")

with degirum_tools.Display("Haptic v6 — 5 Zones") as disp:
    while True:
        frame = camera.capture_array("main")

        # YOLO
        det_result = det_model.predict(frame)
        try:
            tracker.analyze(det_result)
        except:
            pass

        img = tracker.annotate(det_result, det_result.image_overlay)

        # DEPTH
        depth_raw = depth_raw_to_224(depth_model.predict(frame))
        depth_zones = depth_to_zones(depth_raw)

        zone_candidates = {}

        # Depth-first fallback
        for z in range(5):
            d = depth_zones[z]
            if d is not None and d < MAX_DEPTH:
                zone_candidates[z] = ("object", d)

        # YOLO override
        for det in det_result.results:
            label = det["label"].lower()
            x1, y1, x2, y2 = det["bbox"]
            cx, cy = (x1+x2)/2, (y1+y2)/2
            zone = resolve_zone(cx, cy)

            width_px = x2 - x1
            dist = (KNOWN_WIDTH * FOCAL_LENGTH) / \
                width_px if FOCAL_LENGTH else depth_zones[zone]

            prev = zone_candidates.get(zone)
            if prev is None or (dist and dist < prev[1]):
                zone_candidates[zone] = (
                    "person" if label == "person" else "object", dist)

        # Hysteresis update
        for z in range(NUM_MOTORS):
            cand = zone_candidates.get(z)
            sem = None if cand is None else cand[0]
            dist = None if cand is None else cand[1]
            last_semantic[z].append(sem)
            last_dist[z].append(dist)

        # Desired values
        desired = [0]*NUM_MOTORS
        for z in range(NUM_MOTORS):
            sem = last_semantic[z]

            if sem[-1] == "person":
                pattern_state[z]["mode"] = "person"
                desired[z] = perceptual_map(last_dist[z][-1])
                continue

            if len(sem) >= 2 and all(s == "object" for s in sem):
                pattern_state[z]["mode"] = "object"
                desired[z] = perceptual_map(last_dist[z][-1])
                continue

            if len(sem) >= 2 and all(s is None for s in sem):
                pattern_state[z]["mode"] = "none"
                desired[z] = 0
                continue

            desired[z] = pattern_state[z]["last_value"]

        # Final motor output
        tnow = time.time()
        final = [0]*NUM_MOTORS

        for z in range(NUM_MOTORS):
            base = desired[z]
            if pattern_state[z]["mode"] == "person" and base > 0:
                boosted = min(127, base + 80)
                phase = (tnow - pattern_state[z]["hb_start"]
                         ) % (HB_P1 + HB_G + HB_P2 + HB_BASE_REST)
                final[z] = boosted if phase < HB_P1 or (
                    HB_P1+HB_G <= phase < HB_P1+HB_G+HB_P2) else 0
            else:
                final[z] = base

        # I2C writes
        if (tnow - last_update) > UPDATE_INTERVAL:
            for i, val in enumerate(final):
                if abs(val - pattern_state[i]["last_value"]) >= MIN_UPDATE_STEP:
                    drvs[i].realtime_value = val
                    pattern_state[i]["last_value"] = val
            last_update = tnow

        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
