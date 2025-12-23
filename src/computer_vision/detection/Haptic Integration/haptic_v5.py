# person_speed_haptic_test_v3_3_depthfirst_optionA_strongHB.py
# -------------------------------------------------------------
# Version 3.3 + Strong Heartbeat Upgrade
# - Depth-first obstacle detection (Fix #3-6)
# - Person overrides object immediately (Option A)
# - NEW: Distance-adaptive stronger heartbeat intensities
# - Heartbeat = boosted intensity + frequency scaling
# - All motors use MODE_REALTIME

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
NUM_COLUMNS = 7

KNOWN_DISTANCE = 2.5
KNOWN_WIDTH = 0.4

UPDATE_INTERVAL = 0.08
MIN_UPDATE_STEP = 3
MAX_DEPTH = 4.0
MIN_DEPTH = 0.5
PERCEPTUAL_EXP = 0.6

# Heartbeat timing (scaled per distance)
HB_P1 = 0.12
HB_G = 0.08
HB_P2 = 0.12
HB_BASE_REST = 0.6

# Fix #3
VAR_WINDOW_H = 40
VAR_THRESHOLD = 0.006

# Fix #5
OBJ_CONFIRM_FRAMES = 2
EMPTY_CONFIRM_FRAMES = 2

# ------------------- CAMERA & MODELS -------------------
camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (CAM_W, CAM_H), "format": "RGB888"}))
camera.start()
time.sleep(1.2)

depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1", "@local",
                            "/home/rohan/degirum_wearable_device/models")

det_model = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1", "@local",
                          "/home/rohan/degirum_wearable_device/models",
                          overlay_show_labels=False, overlay_show_probabilities=False)

tracker = degirum_tools.ObjectTracker(track_thresh=0.4,
                                      anchor_point=degirum_tools.AnchorPoint.CENTER,
                                      show_overlay=False)

# ------------------- I2C + DRV INIT -------------------
i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

drv_channels = [mux[i] for i in [1, 2, 3, 4, 5, 6, 7]]
drvs = []
for idx, ch in enumerate(drv_channels):
    try:
        time.sleep(0.12)
        d = DRV2605(ch)
        d.mode = MODE_REALTIME
        d.realtime_value = 0
        drvs.append(d)
    except Exception as e:
        print(f"DRV init failed: {e}")

NUM_MOTORS = len(drvs)

# ------------------- UTILS -------------------


def depth_raw_to_224(depth_result):
    raw = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    return ((raw.astype(np.float32) - zero) * scale).reshape((DEPTH_SIZE, DEPTH_SIZE))


def compute_column_stats(depth_raw):
    h, w = depth_raw.shape
    col_w = w // NUM_COLUMNS
    medians, vars_ = [], []

    y0 = max(0, h//2 - VAR_WINDOW_H//2)
    y1 = min(h, y0 + VAR_WINDOW_H)

    for i in range(NUM_COLUMNS):
        x0 = i * col_w
        x1 = (i+1)*col_w if i < NUM_COLUMNS-1 else w

        seg = depth_raw[:, x0:x1]
        medians.append(float(np.nanmedian(seg)))

        center = depth_raw[y0:y1, x0:x1]
        vars_.append(float(np.nanvar(center)))

    return medians, vars_


def perceptual_map(depth_value):
    if depth_value is None or np.isnan(depth_value):
        return 0
    if depth_value >= MAX_DEPTH:
        return 0
    if depth_value <= MIN_DEPTH:
        return 127
    norm = 1.0 - (depth_value - MIN_DEPTH) / (MAX_DEPTH - MIN_DEPTH)
    return int(min(127, max(0, round(math.pow(norm, PERCEPTUAL_EXP) * 127))))


def motors_for_bbox(x1, x2):
    col_w = CAM_W / NUM_COLUMNS
    first = int(max(0, math.floor(x1 / col_w)))
    last = int(min(NUM_COLUMNS-1, math.floor((x2-1)/col_w)))
    return [i for i in range(first, last+1) if i < NUM_MOTORS]


# ------------------- STATE -------------------
last_semantic = [deque(maxlen=2) for _ in range(NUM_MOTORS)]
last_dist = [deque(maxlen=2) for _ in range(NUM_MOTORS)]
pattern_state = {i: {"mode": "none", "hb_start": 0.0, "last_value": 0}
                 for i in range(NUM_MOTORS)}
last_update = 0.0

# ------------------- CALIBRATION -------------------
print("Calibrating with person at 2.5m...")
time.sleep(1.2)
ref = camera.capture_array("main")
res = det_model.predict(ref)
refW = 0
for det in res.results:
    if det["label"].lower() == "person":
        x1, y1, x2, y2 = det["bbox"]
        refW = x2-x1
        break

FOCAL_LENGTH = (refW * KNOWN_DISTANCE) / KNOWN_WIDTH if refW > 0 else None

# ------------------- MAIN LOOP -------------------
print("Running...")

with degirum_tools.Display("v3.3 Strong Heartbeat") as disp:
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
        col_medians, col_vars = compute_column_stats(depth_raw)
        now = time.time()

        column_candidates = {}

        # ---- Depth-first (Fix #3) ----
        for midx, d in enumerate(col_medians):
            if midx >= NUM_MOTORS:
                break
            if d < MAX_DEPTH and col_vars[midx] <= VAR_THRESHOLD:
                column_candidates[midx] = ("depth", d, now)

        # ---- Add YOLO detections ----
        for det in det_result.results:
            label = det["label"].lower()
            x1, y1, x2, y2 = det["bbox"]

            width_px = x2-x1
            if FOCAL_LENGTH:
                dist_bb = (KNOWN_WIDTH * FOCAL_LENGTH) / width_px
            else:
                cols = motors_for_bbox(x1, x2)
                dist_bb = float(np.nanmean([col_medians[c]
                                for c in cols])) if cols else None

            motors = motors_for_bbox(x1, x2)
            for midx in motors:
                old = column_candidates.get(midx)
                if old is None:
                    column_candidates[midx] = (label, dist_bb, now)
                else:
                    _, oldd, _ = old
                    if dist_bb is not None and (oldd is None or dist_bb < oldd):
                        column_candidates[midx] = (label, dist_bb, now)

        # ---- Hysteresis update ----
        candidate_sem = [None]*NUM_MOTORS
        candidate_dist = [None]*NUM_MOTORS

        for midx in range(NUM_MOTORS):
            cand = column_candidates.get(midx)
            if cand is None:
                candidate_sem[midx] = None
                candidate_dist[midx] = None
            else:
                label, distv, _ = cand
                candidate_sem[midx] = "person" if label == "person" else "object"
                candidate_dist[midx] = distv

            last_semantic[midx].append(candidate_sem[midx])
            last_dist[midx].append(candidate_dist[midx])

        # ---- Compute desired values ----
        desired_values = [0]*NUM_MOTORS

        for midx in range(NUM_MOTORS):
            semHist = last_semantic[midx]
            distHist = last_dist[midx]

            # PERSON → immediate
            if len(semHist) >= 1 and semHist[-1] == "person":
                dist_val = distHist[-1]
                if dist_val is None:
                    dist_val = col_medians[midx]

                base_intensity = perceptual_map(dist_val)
                pattern_state[midx]["mode"] = "person"
                desired_values[midx] = base_intensity
                continue

            # OBJECT → 2-frame confirm
            obj_ok = len(semHist) >= OBJ_CONFIRM_FRAMES and all(
                s == "object" for s in list(semHist)[-OBJ_CONFIRM_FRAMES:]
            )
            if obj_ok:
                dval = None
                for d in reversed(distHist):
                    if d is not None:
                        dval = d
                        break
                if dval is None:
                    dval = col_medians[midx]

                base_intensity = perceptual_map(dval)
                pattern_state[midx]["mode"] = "object"
                desired_values[midx] = base_intensity
                continue

            # EMPTY → turn off after 2 frames
            empty_ok = len(semHist) >= EMPTY_CONFIRM_FRAMES and all(
                s is None for s in list(semHist)[-EMPTY_CONFIRM_FRAMES:]
            )
            if empty_ok:
                pattern_state[midx]["mode"] = "none"
                desired_values[midx] = 0
                continue

            desired_values[midx] = pattern_state[midx]["last_value"]

        # ---- Compose final heartbeat / buzz values ----
        final_values = [0]*NUM_MOTORS
        tnow = time.time()

        for midx in range(NUM_MOTORS):
            mode = pattern_state[midx]["mode"]
            base_val = desired_values[midx]

            if mode == "person" and base_val > 0:
                dist_val = last_dist[midx][-1]
                if dist_val is None:
                    dist_val = col_medians[midx]

                # ----------------------------------------
                # NEW STRONG HEARTBEAT BOOST (distance-based)
                # ----------------------------------------
                if dist_val is None:
                    hb_boost = 50
                else:
                    if dist_val > 3:
                        hb_boost = 50
                    elif dist_val > 2:
                        hb_boost = 70
                    elif dist_val > 1:
                        hb_boost = 90
                    else:
                        hb_boost = 110

                boosted = min(127, base_val + hb_boost)
                # ----------------------------------------

                # Frequency scaling
                hb_scale = 1.0 - (boosted/127.0)*0.6

                HB_P1s = HB_P1 * hb_scale
                HB_Gs = HB_G * hb_scale
                HB_P2s = HB_P2 * hb_scale
                HB_PERIOD = HB_P1s + HB_Gs + HB_P2s + HB_BASE_REST*hb_scale

                hb = pattern_state[midx]["hb_start"]
                if hb == 0.0 or (tnow-hb) > HB_PERIOD:
                    pattern_state[midx]["hb_start"] = tnow
                    hb = tnow

                phase = tnow - hb

                if phase < HB_P1s:
                    mult = 1.0
                elif phase < HB_P1s+HB_Gs:
                    mult = 0.0
                elif phase < HB_P1s+HB_Gs+HB_P2s:
                    mult = 1.0
                else:
                    mult = 0.0

                final_values[midx] = int(min(127, max(0, round(boosted*mult))))

            elif mode == "object" and base_val > 0:
                final_values[midx] = base_val
                pattern_state[midx]["hb_start"] = 0.0

            else:
                final_values[midx] = 0
                pattern_state[midx]["hb_start"] = 0.0

        # ---- I2C writes ----
        if (tnow-last_update) >= UPDATE_INTERVAL:
            for midx, val in enumerate(final_values):
                if midx >= NUM_MOTORS:
                    break
                lastv = pattern_state[midx]["last_value"]
                if abs(val-lastv) >= MIN_UPDATE_STEP or (val == 0 and lastv != 0):
                    try:
                        drvs[midx].mode = MODE_REALTIME
                        drvs[midx].realtime_value = val
                        pattern_state[midx]["last_value"] = val
                    except:
                        pass
            last_update = tnow

        # ---- Display ----
        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
