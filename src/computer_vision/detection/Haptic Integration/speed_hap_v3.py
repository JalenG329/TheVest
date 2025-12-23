# person_speed_haptic_test_v3_realtime_dynamicHB_targeted.py
# ----------------------------------------------------------
# Version 3.2: Targeted haptics (only motors under detections)
# - Motors vibrate only when an object or person is detected in their column
# - Person: dynamic heartbeat (amplitude + frequency scale with distance)
# - Object: continuous vibration (distance-based amplitude)
# - Idle columns: no vibration (intensity = 0)
# - Optimized I2C writes for 17–19 FPS real-time feedback

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

# ------------------- CONFIG -------------------
CAM_W, CAM_H = 960, 540
DEPTH_MODEL_SIZE = 224
NUM_COLUMNS = 7
KNOWN_DISTANCE = 2.5
KNOWN_WIDTH = 0.4

UPDATE_INTERVAL = 0.08
MIN_UPDATE_STEP = 3
MAX_DEPTH = 4.0
MIN_DEPTH = 0.5

HB_PULSE1 = 0.12
HB_GAP = 0.08
HB_PULSE2 = 0.12
HB_BASE_PERIOD = HB_PULSE1 + HB_GAP + HB_PULSE2 + 0.6
PERCEPTUAL_EXP = 0.6

# ------------------- CAMERA & MODELS -------------------
camera = Picamera2()
camera.configure(camera.create_preview_configuration(
    main={"size": (CAM_W, CAM_H), "format": "RGB888"}))
camera.start()
time.sleep(1.5)

depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1", "@local",
                            "/home/rohan/degirum_wearable_device/models")
det_model = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1", "@local",
                          "/home/rohan/degirum_wearable_device/models",
                          overlay_show_labels=False, overlay_show_probabilities=False)

tracker = degirum_tools.ObjectTracker(
    track_thresh=0.4,
    anchor_point=degirum_tools.AnchorPoint.CENTER,
    show_overlay=False
)

# ------------------- I2C + MOTOR SETUP -------------------
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
        print(f"✅ DRV initialized on channel {idx+1}")
    except OSError as e:
        print(f"⚠️ DRV init failed on channel {idx+1}: {e}")

NUM_MOTORS = len(drvs)
if NUM_MOTORS < NUM_COLUMNS:
    print(
        f"⚠️ Found {NUM_MOTORS} motors, expected {NUM_COLUMNS}. Mapping truncated.")

# ------------------- UTILS -------------------


def perceptual_map(depth_value, min_d=MIN_DEPTH, max_d=MAX_DEPTH):
    """Map depth (m) -> 0–127 intensity (closer = stronger)."""
    if depth_value is None or np.isnan(depth_value):
        return 0
    if depth_value >= max_d:
        return 0
    if depth_value <= min_d:
        return 127
    normalized = 1.0 - (depth_value - min_d) / (max_d - min_d)
    perceptual = math.pow(normalized, PERCEPTUAL_EXP)
    return int(max(0, min(127, round(perceptual * 127))))


def compute_focal_length(known_distance, real_width, width_in_image):
    return (width_in_image * known_distance) / real_width


def compute_distance(focal_length, real_width, width_in_image):
    if width_in_image <= 0 or focal_length is None:
        return None
    return (real_width * focal_length) / width_in_image


def depth_result_to_map(depth_result):
    raw = depth_result._inference_results[0]['data']
    scale = depth_result._inference_results[0]['quantization']['scale'][0]
    zero = depth_result._inference_results[0]['quantization']['zero'][0]
    depth_map = (raw.astype(np.float32) - zero) * scale
    depth_map = depth_map.reshape((DEPTH_MODEL_SIZE, DEPTH_MODEL_SIZE))
    return cv2.resize(depth_map, (CAM_W, CAM_H), interpolation=cv2.INTER_LINEAR)


def motors_for_bbox(x1, x2):
    """Return motor indices overlapping bbox."""
    col_w = CAM_W / NUM_COLUMNS
    first = int(max(0, math.floor(x1 / col_w)))
    last = int(min(NUM_COLUMNS - 1, math.floor((x2 - 1) / col_w)))
    return [i for i in range(first, last + 1) if i < NUM_MOTORS]


# ------------------- STATE -------------------
pattern_state = {i: {"mode": "none", "hb_start": 0.0, "last_value": 0}
                 for i in range(NUM_MOTORS)}
last_global_update = 0.0

# ------------------- CALIBRATION -------------------
print("Place a person at ~2.5 m for quick calibration...")
time.sleep(1.5)
ref_frame = camera.capture_array("main")
ref_det = det_model.predict(ref_frame)
ref_width = 0
for det in ref_det.results:
    if det.get("label", "").lower() == "person":
        x1, y1, x2, y2 = det["bbox"]
        ref_width = x2 - x1
        break
FOCAL_LENGTH = compute_focal_length(
    KNOWN_DISTANCE, KNOWN_WIDTH, ref_width) if ref_width > 0 else None
if FOCAL_LENGTH:
    print(f"✅ Calibrated focal length: {FOCAL_LENGTH:.2f}px")

# ------------------- MAIN LOOP -------------------
print("Running... Press 'q' to quit.")
with degirum_tools.Display("Haptic v3.2 (Targeted Dynamic Heartbeat)") as disp:
    while True:
        frame = camera.capture_array("main")

        # 1. Object detection
        det_result = det_model.predict(frame)
        try:
            tracker.analyze(det_result)
        except Exception:
            pass
        img = tracker.annotate(det_result, det_result.image_overlay)

        # 2. Depth estimation
        depth_result = depth_model.predict(frame)
        depth_map = depth_result_to_map(depth_result)

        # 3. Build activation map
        zone_activations = {}
        now = time.time()
        for det in det_result.results:
            label = det.get("label", "").lower()
            x1, y1, x2, y2 = det["bbox"]
            width_px = x2 - x1
            if FOCAL_LENGTH:
                bb_dist = compute_distance(FOCAL_LENGTH, KNOWN_WIDTH, width_px)
            else:
                bb_dist = np.nanmean(depth_map[int(y1):int(
                    y2), int(x1):int(x2)]) if y2 > y1 else None
            motors = motors_for_bbox(x1, x2)
            for midx in motors:
                prev = zone_activations.get(midx)
                if prev is None or (label == "person" and prev[0] != "person"):
                    zone_activations[midx] = (label, bb_dist, now)

        # 4. Compute intensities only for detected regions
        desired_values = [0]*NUM_MOTORS
        for midx, info in zone_activations.items():
            label, dist, _ = info
            if dist is not None:
                if dist > 4:
                    intensity = 0
                elif dist > 3:
                    intensity = 40
                elif dist > 2:
                    intensity = 80
                elif dist > 1:
                    intensity = 110
                else:
                    intensity = 127
            else:
                intensity = 80  # default fallback
            pattern_state[midx]["mode"] = "person" if label == "person" else "object"
            desired_values[midx] = intensity

        # 5. Generate heartbeat or steady signal
        final_values = [0]*NUM_MOTORS
        tnow = time.time()
        for midx in range(NUM_MOTORS):
            mode = pattern_state[midx]["mode"]
            base_val = desired_values[midx]
            dist = zone_activations[midx][1] if midx in zone_activations else None

            if mode == "person" and base_val > 0:
                if dist is not None:
                    if dist > 3:
                        hb_scale = 1.0
                    elif dist > 2:
                        hb_scale = 0.8
                    elif dist > 1:
                        hb_scale = 0.6
                    else:
                        hb_scale = 0.4
                else:
                    hb_scale = 1.0

                HB_P1 = HB_PULSE1 * hb_scale
                HB_G = HB_GAP * hb_scale
                HB_P2 = HB_PULSE2 * hb_scale
                HB_PERIOD = HB_P1 + HB_G + HB_P2 + (0.6 * hb_scale)

                hb = pattern_state[midx].get("hb_start", 0.0)
                if hb == 0.0 or (tnow - hb) > HB_PERIOD:
                    pattern_state[midx]["hb_start"] = tnow
                    hb = tnow
                phase = tnow - hb

                if 0 <= phase < HB_P1:
                    mult = 1.0
                elif HB_P1 <= phase < HB_P1 + HB_G:
                    mult = 0.0
                elif HB_P1 + HB_G <= phase < HB_P1 + HB_G + HB_P2:
                    mult = 1.0
                else:
                    mult = 0.0
                final = int(round(base_val * mult))
            elif mode == "object" and base_val > 0:
                final = int(round(base_val))
                pattern_state[midx]["hb_start"] = 0.0
            else:
                final = 0
                pattern_state[midx]["hb_start"] = 0.0

            final_values[midx] = max(0, min(127, final))

        # 6. Write to motors (minimal I2C updates)
        if (tnow - last_global_update) >= UPDATE_INTERVAL:
            for midx, val in enumerate(final_values):
                if midx >= NUM_MOTORS:
                    break
                last = pattern_state[midx]["last_value"]
                if abs(val - last) >= MIN_UPDATE_STEP or (val == 0 and last != 0):
                    try:
                        drvs[midx].mode = MODE_REALTIME
                        drvs[midx].realtime_value = val
                        pattern_state[midx]["last_value"] = val
                    except OSError as e:
                        print(f"⚠️ I2C error on motor {midx}: {e}")
            last_global_update = tnow

        disp.show(img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.close()
cv2.destroyAllWindows()
