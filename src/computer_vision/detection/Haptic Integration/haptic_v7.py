# haptic_v7_fixed.py
# ---------------------------------------------------------
# 5-Zone Haptic Navigation System (FIXED DRV2605 INIT)
# ---------------------------------------------------------

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
BOTTOM_ZONE_RATIO = 0.20

MAX_DEPTH = 4.0
MIN_DEPTH = 0.5

UPDATE_INTERVAL = 0.08
MIN_UPDATE_STEP = 3

CONFIRM_FRAMES = 2
EMPTY_FRAMES = 2

# STOP navigation
CYCLE_PERIOD = 1.4
CYCLE_DROP = 25

STOP_DIST_LEVELS = [
    (3.0, 60),
    (2.0, 75),
    (1.2, 105),
    (0.5, 127)
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

# Motor order
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
    try:
        time.sleep(0.12)
        d = DRV2605(mux[ch])   # ✅ FIXED
        d.mode = MODE_REALTIME
        d.realtime_value = 0
        drvs.append(d)
        print(f"[INIT] DRV2605 ready on mux channel {ch}")
    except Exception as e:
        print(f"[ERROR] DRV init failed on channel {ch}: {e}")

# ===================== HELPERS =====================


def depth_raw(res):
    raw = res._inference_results[0]['data']
    scale = res._inference_results[0]['quantization']['scale'][0]
    zero = res._inference_results[0]['quantization']['zero'][0]
    return ((raw.astype(np.float32) - zero) * scale).reshape((DEPTH_SIZE, DEPTH_SIZE))


def stop_intensity(dist):
    for d, level in STOP_DIST_LEVELS:
        if dist > d:
            return level
    return 127


def exponential_cycle(stage, t):
    start = max(0, stage - CYCLE_DROP)
    phase = (t % CYCLE_PERIOD) / CYCLE_PERIOD
    return int(min(stage, start * math.exp(phase * math.log(stage / start))))


# ===================== STATE =====================
semantic_hist = [deque(maxlen=CONFIRM_FRAMES) for _ in range(NUM_ZONES)]
dist_hist = [deque(maxlen=CONFIRM_FRAMES) for _ in range(NUM_ZONES)]
last_val = [0] * NUM_ZONES
last_update = 0.0

# ===================== MAIN LOOP =====================
print("System running. Press 'q' to exit.")

with degirum_tools.Display("Haptic v7 Fixed") as disp:
    while True:
        frame = camera.capture_array("main")

        det_res = det_model.predict(frame)
        try:
            tracker.analyze(det_res)
        except:
            pass
        img = tracker.annotate(det_res, det_res.image_overlay)

        depth_map = depth_raw(depth_model.predict(frame))
        h, w = depth_map.shape
        bottom_cut = int(h * (1 - BOTTOM_ZONE_RATIO))

        zone_depth = [None] * NUM_ZONES
        col_w = w // 4

        for i in range(4):
            zone_depth[i] = float(np.nanmedian(
                depth_map[:bottom_cut, i*col_w:(i+1)*col_w]))

        zone_depth[4] = float(np.nanmedian(depth_map[bottom_cut:, :]))

        candidates = {}

        for det in det_res.results:
            label = det["label"].lower()
            x1, _, x2, _ = det["bbox"]
            cx = (x1 + x2) / 2
            zone = min(3, int(cx / (CAM_W / 4)))
            candidates[zone] = (label, zone_depth[zone])

        if zone_depth[4] < MAX_DEPTH:
            candidates[4] = ("object", zone_depth[4])

        for i in range(NUM_ZONES):
            if i in candidates:
                semantic_hist[i].append(candidates[i][0])
                dist_hist[i].append(candidates[i][1])
            else:
                semantic_hist[i].append(None)
                dist_hist[i].append(None)

        desired = [0] * NUM_ZONES
        now = time.time()

        for i in range(NUM_ZONES):
            sems = list(semantic_hist[i])
            dists = list(dist_hist[i])

            if sems[-1] == "person":
                desired[i] = 110
            elif "stop sign" in sems:
                d = next((x for x in reversed(dists) if x), 2.5)
                desired[i] = exponential_cycle(stop_intensity(d), now)
            elif sems.count("object") >= CONFIRM_FRAMES:
                desired[i] = 80
            elif sems.count(None) >= EMPTY_FRAMES:
                desired[i] = 0

        if now - last_update > UPDATE_INTERVAL:
            for i, val in enumerate(desired):
                if abs(val - last_val[i]) >= MIN_UPDATE_STEP or val == 0:
                    drvs[i].realtime_value = int(val)
                    last_val[i] = int(val)

                    print(f"[HAPTIC] {MOTOR_LABELS[i]} | Intensity: {val}")

            last_update = now

        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
