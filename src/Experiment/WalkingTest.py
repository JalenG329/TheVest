

# # guide_minimal.py
# # ============================================================
# # MINIMAL GUIDE: the core idea, plus only the safeguards that fixed
# # real problems during testing. Read it top to bottom.
# #
# #   camera frame -> FastDepth -> 7 numbers -> if/else -> motors
# #
# #   Motors (wearer's view):  FRONT 6 7 2 0  /  BACK 4 5 3 1
# #     6, 4 = go LEFT     0, 1 = go RIGHT     3 = BLOCKED / STOP
# #     nothing buzzing = path is clear
# #
# #   FastDepth numbers: LOWER = CLOSER (not real meters).
# # ============================================================

# import os # import os for directory creation and file handling
# import csv  #import csv for logging data in CSV format
# import time #import time for timing and sleep functions
# import signal   #import signal for handling termination signals
# import threading    #import threading for running the motor loop in a separate thread meaning the main loop can continue to run without being blocked by the motor loop

# import numpy as np
# import degirum as dg
# from picamera2 import Picamera2
# import board
# import busio
# import adafruit_tca9548a
# from adafruit_drv2605 import DRV2605, MODE_REALTIME


# # ---------------- SETTINGS ----------------
# #  Depth thresholds (meters) and other parameters
# AHEAD_DEPTH = 2.4      # your path reads closer than this -> guide
# STOP_DEPTH = 1.25      # your path reads closer than this -> STOP
# MAX_DEPTH = 2.5        # anything farther is ignored ("nothing close")
# SIDE_DIFF = 0.15       # how much more open a side must be to pick it (0-1 scale)
# SMOOTHING = 0.3        # weight of the newest frame: lower = steadier but slower
# CONFIRM_FRAMES = 3     # a new cue must repeat this many frames (STOP is instant)

# USE_YOLO = True        # catch people/chairs that depth misses
# YOLO_NEAR = 0.40       # box at least this tall = NEAR (even if depth says clear)
# YOLO_STOP = 0.90       # box at least this tall = STOP (even if depth says clear)

# STRENGTH = 127                     # motor strength, 0-127
# PULSE_ON = 0.15                    # each pulse lasts this long (seconds)
# FAR_GAP, NEAR_GAP = 0.70, 0.10     # pause between pulses: far -> near
# STOP_GAP = 0.05                    # pause between STOP pulses (rapid)

# LEFT_MOTORS = [6, 4]
# RIGHT_MOTORS = [0, 1]
# STOP_MOTORS = [3]                  # motor 5 is broken, so only 3 for now

# LOG = True             # CSV log in logs/ (works with compare_logs.py)
# PRINT_EVERY = 10       # status line every N frames (and whenever the cue changes)
# PRINT_TIMING = False   # True = also print how long each step takes (for speed comparisons)
# MODELS_DIR = "/home/rohan/degirum_wearable_device/models"
# YOLO_DIR = "/home/rohan/haptic feedback vest final/models"
# OBSTACLES = {"person", "chair", "bench", "couch", "backpack", "suitcase"}


# # ---------------- MOTORS ----------------
# # The main loop sets `pattern`; a small background thread does the pulsing,
# # so pulse timing stays steady even when a camera frame is slow.

# motors = {} # channel -> DRV2605 object
# pattern = ([], 0.0) # the current pattern: (active channels, gap between pulses)
# running = True  # whether the motor loop is running


# # ---------------- MOTOR HELPERS ----------------
# def connect_motor(ch):  # connect to a motor driver on the given TCA channel, return DRV2605 object
#     drv = DRV2605(tca[ch])  # connect to the DRV2605 driver on the given TCA channel
#     drv.mode = MODE_REALTIME  # "set the strength directly" mode
#     drv.realtime_value = 0  # start with the motor off
#     return drv  # return the DRV2605 object for the motor driver


# def set_motors(active, strength):   # set the given motors to the given strength, and turn off all others
#     for ch, drv in motors.items():  # iterate over all motors
#         try:
#             drv.realtime_value = strength if ch in active else 0    # set the strength of the motor to the given strength if it is in the active list, otherwise set it to 0 (off)
#         except Exception:
#             pass                   # a failed write is retried on the next pulse


# def wait(seconds, current):  # Check for a new pattern every 10ms, but don't block the motor thread for too long
#     end = time.monotonic() + seconds
#     while running and pattern == current and time.monotonic() < end:
#         time.sleep(0.01)


# def fix_reset_drivers():    # check all motor drivers and reconnect if needed
#     """A power dip resets a driver chip into standby, where it ignores us."""
#     for ch, drv in list(motors.items()):
#         try:
#             if drv.mode != MODE_REALTIME:   # if the driver is not in realtime mode, it has reset
#                 motors[ch] = connect_motor(ch)
#                 print(f"motor {ch} driver had reset (power dip) - restored")
#         except Exception:
#             pass


# def motor_loop():
#     last_check = time.monotonic()
#     while running:
#         current = pattern
#         active, gap = current
#         if active:
#             set_motors(active, STRENGTH)   # pulse on
#             wait(PULSE_ON, current)
#             set_motors([], 0)              # pulse off
#             wait(gap, current)
#         else:
#             set_motors([], 0)
#             wait(0.05, current)
#         if time.monotonic() - last_check > 1.0:   # once a second
#             fix_reset_drivers()
#             last_check = time.monotonic()


# # ---------------- DEPTH ---------------
# # Depth estimation from the camera frame
# def get_strips(frame):  #return 7 numbers (left to right) representing the median depth in each vertical strip of the frame, ignoring the ceiling and floor. The depth is scaled to meters using the quantization parameters from the model output.
#     out = depth_model.predict(frame)._inference_results[0]  # run the depth model on the frame and get the output
#     q = out["quantization"] # get the quantization parameters from the model output
#     depth = (out["data"].astype(np.float32) - q["zero"][0]) * q["scale"][0] # scale the output data to meters using the quantization parameters
#     depth = depth.reshape(224, 224) # reshape the output data to a 224x224 array
#     band = depth[56:179]               # rows 25%-80%: skip ceiling and the floor at your feet
#     return np.array([np.median(s) for s in np.array_split(band, 7, axis=1)])


# #A function that takes a depth value (in meters) and returns a closeness value between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). 
# def closeness(d):   
#     return np.clip((MAX_DEPTH - d) / (MAX_DEPTH - 0.5), 0, 1)   #clip the closeness value to be between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). The formula used is (MAX_DEPTH - d) / (MAX_DEPTH - 0.5), which scales the depth value to a closeness value between 0 and 1.


# # ---------------- THE DECISION (plain if/else) ----------------
# def decide(strips, box_h, box_x):
#     ahead = np.median(strips[2:5])            # middle 3 strips = your path
#     left = np.mean(closeness(strips[0:3]))    # average closeness on the left
#     right = np.mean(closeness(strips[4:7]))   # average closeness on the right

#     if ahead <= STOP_DEPTH or box_h >= YOLO_STOP:   # if the path ahead is too close or YOLO sees a very close obstacle, then stop
#         return "STOP"
#     if ahead >= AHEAD_DEPTH and box_h < YOLO_NEAR:  # if the path ahead is clear and YOLO does not see a close obstacle, then continue straight
#         return "CLEAR"
#     if left - right >= SIDE_DIFF:   # if the left side is significantly more open than the right side, then turn right
#         return "RIGHT"                        
#     if right - left >= SIDE_DIFF:
#         return "LEFT"
#     if box_h >= YOLO_NEAR:                    # if YOLO sees a close obstacle, then turn away from it
#         return "RIGHT" if box_x < 0.5 else "LEFT"  # if the obstacle is on the left side, turn right; if it is on the right side, turn left
#     return "BLOCKED"    # if the path is blocked and there is no clear direction to turn, then return "BLOCKED"


# def pulse_gap(strips, box_h):
#     """Closer obstacle -> shorter pause -> faster pulses (4 speeds)."""
#     ahead = np.median(strips[2:5])  # middle 3 strips = your path
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1) #assign urgency based on depth
#     if box_h >= YOLO_NEAR:  # YOLO sees someone in your way -> increase urgency
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))   # increase urgency based on box height
#     urgency = round(min(urgency, 1.0) * 3) / 3  # round to 0, 1/3, 2/3, 1
#     return FAR_GAP + (NEAR_GAP - FAR_GAP) * urgency # scale gap based on urgency


# def get_urgency(strips, box_h):
#     """Urgency for the status line: 0 = just noticed ... 1 = at STOP distance (same math as pulse_gap)."""
#     ahead = np.median(strips[2:5])
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1)
#     if box_h >= YOLO_NEAR:
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))
#     return float(min(urgency, 1.0))


# # ---------------- STOP SAFELY ----------------
# def stop_on_signal(signum, frame):
#     raise KeyboardInterrupt          # VS Code stop button / closed terminal -> normal shutdown


# signal.signal(signal.SIGTERM, stop_on_signal)
# signal.signal(signal.SIGHUP, stop_on_signal)


# # ---------------- MAIN ----------------
# def main():
#     global tca, depth_model, pattern, running
#     camera = thread = log_file = None
#     try:
#         print("Loading models...")
#         depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1",
#                                     "@local", MODELS_DIR)
#         yolo = None
#         if USE_YOLO:
#             yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
#                                  "@local", YOLO_DIR)
#             yolo.input_numpy_colorspace = "BGR"     # Pi camera frames are stored B,G,R

#         camera = Picamera2()
#         camera.configure(camera.create_preview_configuration(
#             main={"size": (640, 360), "format": "RGB888"}))
#         camera.start()
#         time.sleep(1.0)

#         tca = adafruit_tca9548a.TCA9548A(busio.I2C(board.SCL, board.SDA))
#         for ch in LEFT_MOTORS + RIGHT_MOTORS + STOP_MOTORS:
#             try:
#                 motors[ch] = connect_motor(ch)
#             except Exception as e:
#                 print(f"Motor {ch} unavailable: {e}")
#         thread = threading.Thread(target=motor_loop, daemon=True)
#         thread.start()

#         if LOG:
#             os.makedirs("logs", exist_ok=True)
#             log_file = open(f"logs/guide_minimal_{time.strftime('%Y%m%d_%H%M%S')}.csv",
#                             "w", newline="", buffering=1)
#             log = csv.writer(log_file)
#             log.writerow(["time", "frame_ms", "L", "C", "R", "state", "intensity", "yolo_near",
#                           "yolo_h", "yolo_label"])

#         print("\nGUIDE MINIMAL running | Ctrl+C to quit\n")
#         smooth = None
#         cue, candidate, count = "CLEAR", None, 0    # the current cue, the candidate cue, and the count of consecutive frames for the candidate cue
#         box_h, box_x = 0.0, 0.5 # the height and x position of the tallest YOLO box in the middle third of the frame
#         box_label = ""          # the class of that box 
#         frame_no = 0    # the number of frames processed
#         last_cue = None # the cue printed last time (so we print whenever it changes)
#         timing = {"camera": 0.0, "depth": 0.0, "yolo": 0.0, "logic": 0.0}

#         while True:
#             t0 = time.monotonic()

#             # 1. camera
#             frame = camera.capture_array("main")
#             t1 = time.monotonic()

#             # 2. depth -> 7 numbers, smoothed over time
#             strips = get_strips(frame)
#             smooth = strips if smooth is None else SMOOTHING * strips + (1 - SMOOTHING) * smooth    # smooth the depth readings over time to reduce noise and fluctuations
#             t2 = time.monotonic()

#             # 3. YOLO (every 2nd frame to save time): tallest obstacle in the middle third
#             frame_no += 1
#             if yolo and frame_no % 2 == 0:  # run YOLO every 2nd frame to save time
#                 box_h, box_x = 0.0, 0.5 # reset the tallest box height and x position
#                 box_label = ""
#                 for det in yolo.predict(frame).results:
#                     if det.get("label") in OBSTACLES and det.get("score", 0) >= 0.4:    # if the detected object is in the list of obstacles and the confidence score is at least 0.4
#                         x1, y1, x2, y2 = det["bbox"]    # get the bounding box coordinates of the detected object
#                         x, h = (x1 + x2) / 2 / 640, (y2 - y1) / 360  # calculate the center x position and height of the bounding box, normalized to the frame size
#                         if 0.33 <= x <= 0.67 and h > box_h:  # if the bounding box is in the middle third of the frame and taller than the previous tallest box, update the tallest box height and x position
#                             box_h, box_x = h, x
#                             box_label = det.get("label")
#             t3 = time.monotonic()   # YOLO timing

#             # 4. decide, then only switch after CONFIRM_FRAMES agreeing frames
#             new = decide(smooth, box_h, box_x)  # decide what to do based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             if new == "STOP" or new == cue: # if the new cue is STOP or the same as the current cue, then switch immediately
#                 cue, count = new, 0
#             elif new == candidate:  # if the new cue is the same as the candidate cue, then increment the count of consecutive frames for the candidate cue
#                 count += 1
#                 if count >= CONFIRM_FRAMES: # if the count of consecutive frames for the candidate cue is at least CONFIRM_FRAMES, then switch to the candidate cue
#                     cue, count = new, 0
#             else:
#                 candidate, count = new, 1

#             # 5. tell the motor thread what to do
#             if cue == "STOP":
#                 pattern = (STOP_MOTORS, STOP_GAP)
#             elif cue == "LEFT":
#                 pattern = (LEFT_MOTORS, pulse_gap(smooth, box_h))   # if the cue is LEFT, then set the pattern to the left motors and the pulse gap based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             elif cue == "RIGHT":
#                 pattern = (RIGHT_MOTORS, pulse_gap(smooth, box_h))
#             elif cue == "BLOCKED":
#                 pattern = (STOP_MOTORS, pulse_gap(smooth, box_h))
#             else:
#                 pattern = ([], 0.0)
#             t4 = time.monotonic()

#             # # 6. timing printout every 30 frames
#             # for name, ms in (("camera", t1 - t0), ("depth", t2 - t1), ("yolo", t3 - t2), ("logic", t4 - t3)):# calculate the time taken for each step in milliseconds and add it to the timing dictionary
#             #     timing[name] += ms * 1000
#             # if frame_no % 30 == 0:  # every 30 frames, print the average timing for each step and the total time taken for all steps, as well as the frames per second (FPS) and the current cue
#             #     total = sum(timing.values()) / 30
#             #     print("TIMING (avg ms)  " + " | ".join(f"{k} {v / 30:.1f}" for k, v in timing.items())
#             #           + f" | total {total:.1f} | FPS {1000 / total:.1f} | cue {cue}")
#             #     timing = dict.fromkeys(timing, 0.0)

#             if cue != last_cue or frame_no % PRINT_EVERY == 0:
#                 obstacle = f"{box_label} (h {box_h:.2f})" if box_h >= YOLO_NEAR else "none"
#                 print(f"{cue:8s} | depth L {np.median(smooth[0:3]):.2f} C {np.median(smooth[2:5]):.2f}"
#                       f" R {np.median(smooth[4:7]):.2f}"
#                       f" | close L {np.mean(closeness(smooth[0:3])):.2f} R {np.mean(closeness(smooth[4:7])):.2f}"
#                       f" | urgency {get_urgency(smooth, box_h):.2f} | obstacle {obstacle}")
#                 last_cue = cue

#             # 7. log to CSV
#             if LOG:
#                 log.writerow([f"{time.time():.3f}", f"{(t4 - t0) * 1000:.3f}",  
#                               f"{np.mean(closeness(smooth[0:3])):.3f}", f"{np.median(smooth[2:5]):.3f}",
#                               f"{np.mean(closeness(smooth[4:7])):.3f}", cue,
#                               STRENGTH if cue != "CLEAR" else 0, int(box_h >= YOLO_NEAR),
#                               f"{box_h:.2f}", box_label])

#     except KeyboardInterrupt:
#         print("\nStopped.")
#     finally:
#         running = False                     # stop the motor thread...
#         if thread:
#             thread.join(timeout=1)
#         for drv in motors.values():         # ...then make sure every motor is off
#             try:
#                 drv.realtime_value = 0
#                 drv._write_u8(0x01, 0x40)   # standby: outputs fully off
#             except Exception:
#                 pass
#         if camera:
#             camera.stop()
#         if log_file:
#             log_file.close()
#         print("System stopped.")


# if __name__ == "__main__":
#     main()



































# # guide_minimal.py
# # ============================================================
# # MINIMAL GUIDE: the core idea, plus only the safeguards that fixed
# # real problems during testing. Read it top to bottom.
# #
# #   camera frame -> FastDepth -> 7 numbers -> if/else -> motors
# #
# #   Motors (wearer's view):  FRONT 6 7 2 0  /  BACK 4 5 3 1
# #     6, 4 = go LEFT     0, 1 = go RIGHT     3 = BLOCKED / STOP
# #     nothing buzzing = path is clear
# #
# #   FastDepth numbers: LOWER = CLOSER (not real meters).
# # ============================================================

# import os # import os for directory creation and file handling
# import csv  #import csv for logging data in CSV format
# import time #import time for timing and sleep functions
# import signal   #import signal for handling termination signals
# import threading    #import threading for running the motor loop in a separate thread meaning the main loop can continue to run without being blocked by the motor loop

# import numpy as np
# import degirum as dg
# from picamera2 import Picamera2
# import board
# import busio
# import adafruit_tca9548a
# from adafruit_drv2605 import DRV2605, MODE_REALTIME


# # ---------------- SETTINGS ----------------
# #  Depth thresholds (meters) and other parameters
# AHEAD_DEPTH = 2.4      # your path reads closer than this -> guide
# STOP_DEPTH = 1.25      # your path reads closer than this -> STOP
# MAX_DEPTH = 2.5        # anything farther is ignored ("nothing close")
# SIDE_DIFF = 0.15       # how much more open a side must be to pick it (0-1 scale)
# SMOOTHING = 0.3        # weight of the newest frame: lower = steadier but slower
# CONFIRM_FRAMES = 3     # a new cue must repeat this many frames (STOP is instant)
# STOP_EXIT = 1.35       # NEW: once stopped, stay stopped until your path reads farther than this
# KEEP_SIDE = 0.075      # NEW: once turning, keep turning until the sides differ by less than this
# YOLO_PUSH = 0.6        # NEW: how strongly an off-center YOLO box pushes you to the other side
# YOLO_SIDE = 0.02       # NEW: with a YOLO obstacle ahead, even a small side difference picks a side

# USE_YOLO = True        # catch people/chairs that depth misses
# YOLO_NEAR = 0.40       # box at least this tall = NEAR (even if depth says clear)
# YOLO_STOP = 0.90       # box at least this tall = STOP (even if depth says clear)

# STRENGTH = 127                     # motor strength, 0-127
# PULSE_ON = 0.15                    # each pulse lasts this long (seconds)
# FAR_GAP, NEAR_GAP = 0.70, 0.10     # pause between pulses: far -> near
# STOP_GAP = 0.05                    # pause between STOP pulses (rapid)

# LEFT_MOTORS = [6, 4]
# RIGHT_MOTORS = [0, 1]
# STOP_MOTORS = [3]                  # motor 5 is broken, so only 3 for now

# LOG = True             # CSV log in logs/ (works with compare_logs.py)
# PRINT_EVERY = 10       # status line every N frames (and whenever the cue changes)
# PRINT_TIMING = False   # True = also print how long each step takes (for speed comparisons)
# MODELS_DIR = "/home/rohan/degirum_wearable_device/models"
# YOLO_DIR = "/home/rohan/haptic feedback vest final/models"
# OBSTACLES = {"person", "chair", "bench", "couch", "backpack", "suitcase"}


# # ---------------- MOTORS ----------------
# # The main loop sets `pattern`; a small background thread does the pulsing,
# # so pulse timing stays steady even when a camera frame is slow.

# motors = {} # channel -> DRV2605 object
# pattern = ([], 0.0) # the current pattern: (active channels, gap between pulses)
# running = True  # whether the motor loop is running


# # ---------------- MOTOR HELPERS ----------------
# def connect_motor(ch):  # connect to a motor driver on the given TCA channel, return DRV2605 object
#     drv = DRV2605(tca[ch])  # connect to the DRV2605 driver on the given TCA channel
#     drv.mode = MODE_REALTIME  # "set the strength directly" mode
#     drv.realtime_value = 0  # start with the motor off
#     return drv  # return the DRV2605 object for the motor driver


# def set_motors(active, strength):   # set the given motors to the given strength, and turn off all others
#     for ch, drv in motors.items():  # iterate over all motors
#         try:
#             drv.realtime_value = strength if ch in active else 0    # set the strength of the motor to the given strength if it is in the active list, otherwise set it to 0 (off)
#         except Exception:
#             pass                   # a failed write is retried on the next pulse


# def wait(seconds, current):  # Check for a new pattern every 10ms, but don't block the motor thread for too long
#     end = time.monotonic() + seconds
#     while running and pattern == current and time.monotonic() < end:
#         time.sleep(0.01)


# def fix_reset_drivers():    # check all motor drivers and reconnect if needed
#     """A power dip resets a driver chip into standby, where it ignores us."""
#     for ch, drv in list(motors.items()):
#         try:
#             if drv.mode != MODE_REALTIME:   # if the driver is not in realtime mode, it has reset
#                 motors[ch] = connect_motor(ch)
#                 print(f"motor {ch} driver had reset (power dip) - restored")
#         except Exception:
#             pass


# def motor_loop():
#     last_check = time.monotonic()
#     while running:
#         current = pattern
#         active, gap = current
#         if active:
#             set_motors(active, STRENGTH)   # pulse on
#             wait(PULSE_ON, current)
#             set_motors([], 0)              # pulse off
#             wait(gap, current)
#         else:
#             set_motors([], 0)
#             wait(0.05, current)
#         if time.monotonic() - last_check > 1.0:   # once a second
#             fix_reset_drivers()
#             last_check = time.monotonic()


# # ---------------- DEPTH ---------------
# # Depth estimation from the camera frame
# def get_strips(frame):  #return 7 numbers (left to right) representing the median depth in each vertical strip of the frame, ignoring the ceiling and floor. The depth is scaled to meters using the quantization parameters from the model output.
#     out = depth_model.predict(frame)._inference_results[0]  # run the depth model on the frame and get the output
#     q = out["quantization"] # get the quantization parameters from the model output
#     depth = (out["data"].astype(np.float32) - q["zero"][0]) * q["scale"][0] # scale the output data to meters using the quantization parameters
#     depth = depth.reshape(224, 224) # reshape the output data to a 224x224 array
#     band = depth[56:179]               # rows 25%-80%: skip ceiling and the floor at your feet
#     return np.array([np.median(s) for s in np.array_split(band, 7, axis=1)])


# #A function that takes a depth value (in meters) and returns a closeness value between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). 
# def closeness(d):   
#     return np.clip((MAX_DEPTH - d) / (MAX_DEPTH - 0.5), 0, 1)   #clip the closeness value to be between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). The formula used is (MAX_DEPTH - d) / (MAX_DEPTH - 0.5), which scales the depth value to a closeness value between 0 and 1.


# # ---------------- THE DECISION (plain if/else) ----------------
# def decide(strips, box_h, box_x, cue):
#     ahead = np.median(strips[2:5])            # middle 3 strips = your path
#     left = np.mean(closeness(strips[0:3]))    # average closeness on the left
#     right = np.mean(closeness(strips[4:7]))   # average closeness on the right

#     stop_at = STOP_EXIT if cue == "STOP" else STOP_DEPTH   # NEW: already stopped -> stay stopped until clearly farther
#     if ahead <= stop_at or box_h >= YOLO_STOP:   # if the path ahead is too close or YOLO sees a very close obstacle, then stop
#         return "STOP"
#     if ahead >= AHEAD_DEPTH and box_h < YOLO_NEAR:  # if the path ahead is clear and YOLO does not see a close obstacle, then continue straight
#         return "CLEAR"

#     diff = left - right                       # NEW: > 0 means the left side has more close stuff
#     right_needed = KEEP_SIDE if cue == "RIGHT" else SIDE_DIFF   # NEW: already turning right -> easier to keep turning right
#     left_needed = KEEP_SIDE if cue == "LEFT" else SIDE_DIFF     # NEW: (switching sides still needs the full SIDE_DIFF)
#     if box_h >= YOLO_NEAR:                    # if YOLO sees a close obstacle, then turn away from it
#         diff += (0.5 - box_x) * YOLO_PUSH     # if the obstacle is on the left side, turn right; if it is on the right side, turn left
#         right_needed = min(right_needed, YOLO_SIDE)   # NEW: with a YOLO obstacle, any real difference picks a side
#         left_needed = min(left_needed, YOLO_SIDE)     # NEW
#     if diff >= right_needed:   # if the left side is significantly more open than the right side, then turn right
#         return "RIGHT"                        
#     if -diff >= left_needed:
#         return "LEFT"
#     return "BLOCKED"    # if the path is blocked and there is no clear direction to turn, then return "BLOCKED"


# def pulse_gap(strips, box_h):
#     """Closer obstacle -> shorter pause -> faster pulses (4 speeds)."""
#     ahead = np.median(strips[2:5])  # middle 3 strips = your path
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1) #assign urgency based on depth
#     if box_h >= YOLO_NEAR:  # YOLO sees someone in your way -> increase urgency
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))   # increase urgency based on box height
#     urgency = round(min(urgency, 1.0) * 3) / 3  # round to 0, 1/3, 2/3, 1
#     return FAR_GAP + (NEAR_GAP - FAR_GAP) * urgency # scale gap based on urgency


# def get_urgency(strips, box_h):   # NEW
#     """NEW: urgency for the status line: 0 = just noticed ... 1 = at STOP distance (same math as pulse_gap)."""
#     ahead = np.median(strips[2:5])
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1)
#     if box_h >= YOLO_NEAR:
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))
#     return float(min(urgency, 1.0))


# # ---------------- STOP SAFELY ----------------
# def stop_on_signal(signum, frame):
#     raise KeyboardInterrupt          # VS Code stop button / closed terminal -> normal shutdown


# signal.signal(signal.SIGTERM, stop_on_signal)
# signal.signal(signal.SIGHUP, stop_on_signal)


# # ---------------- MAIN ----------------
# def main():
#     global tca, depth_model, pattern, running
#     camera = thread = log_file = None
#     try:
#         print("Loading models...")
#         depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1",
#                                     "@local", MODELS_DIR)
#         yolo = None
#         if USE_YOLO:
#             yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
#                                  "@local", YOLO_DIR)
#             yolo.input_numpy_colorspace = "BGR"     # Pi camera frames are stored B,G,R

#         camera = Picamera2()
#         camera.configure(camera.create_preview_configuration(
#             main={"size": (640, 360), "format": "RGB888"}))
#         camera.start()
#         time.sleep(1.0)

#         tca = adafruit_tca9548a.TCA9548A(busio.I2C(board.SCL, board.SDA))
#         for ch in LEFT_MOTORS + RIGHT_MOTORS + STOP_MOTORS:
#             try:
#                 motors[ch] = connect_motor(ch)
#             except Exception as e:
#                 print(f"Motor {ch} unavailable: {e}")
#         thread = threading.Thread(target=motor_loop, daemon=True)
#         thread.start()

#         if LOG:
#             os.makedirs("logs", exist_ok=True)
#             log_file = open(f"logs/guide_minimal_{time.strftime('%Y%m%d_%H%M%S')}.csv",
#                             "w", newline="", buffering=1)
#             log = csv.writer(log_file)
#             log.writerow(["time", "frame_ms", "L", "C", "R", "state", "intensity", "yolo_near",
#                           "yolo_h", "yolo_label"])   # NEW: the last two columns

#         print("\nGUIDE MINIMAL running | Ctrl+C to quit\n")
#         smooth = None
#         cue, candidate, count = "CLEAR", None, 0    # the current cue, the candidate cue, and the count of consecutive frames for the candidate cue
#         box_h, box_x = 0.0, 0.5 # the height and x position of the tallest YOLO box in the middle third of the frame
#         box_label = ""          # the class of that box 
#         frame_no = 0    # the number of frames processed
#         last_cue = None # NEW: the cue printed last time (so we print whenever it changes)
#         timing = {"camera": 0.0, "depth": 0.0, "yolo": 0.0, "logic": 0.0}

#         while True:
#             t0 = time.monotonic()

#             # 1. camera
#             frame = camera.capture_array("main")
#             t1 = time.monotonic()

#             # 2. depth -> 7 numbers, smoothed over time
#             strips = get_strips(frame)
#             smooth = strips if smooth is None else SMOOTHING * strips + (1 - SMOOTHING) * smooth    # smooth the depth readings over time to reduce noise and fluctuations
#             t2 = time.monotonic()

#             # 3. YOLO (every 2nd frame to save time): tallest obstacle in the middle third
#             frame_no += 1
#             if yolo and frame_no % 2 == 0:  # run YOLO every 2nd frame to save time
#                 box_h, box_x = 0.0, 0.5 # reset the tallest box height and x position
#                 box_label = ""          # NEW
#                 for det in yolo.predict(frame).results:
#                     if det.get("label") in OBSTACLES and det.get("score", 0) >= 0.4:    # if the detected object is in the list of obstacles and the confidence score is at least 0.4
#                         x1, y1, x2, y2 = det["bbox"]    # get the bounding box coordinates of the detected object
#                         x, h = (x1 + x2) / 2 / 640, (y2 - y1) / 360  # calculate the center x position and height of the bounding box, normalized to the frame size
#                         if 0.33 <= x <= 0.67 and h > box_h:  # if the bounding box is in the middle third of the frame and taller than the previous tallest box, update the tallest box height and x position
#                             box_h, box_x = h, x
#                             box_label = det.get("label")   # NEW
#             t3 = time.monotonic()   # YOLO timing

#             # 4. decide, then only switch after CONFIRM_FRAMES agreeing frames
#             new = decide(smooth, box_h, box_x, cue)  # decide what to do based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             if new == "STOP" or new == cue: # if the new cue is STOP or the same as the current cue, then switch immediately
#                 cue, count = new, 0
#             elif new == candidate:  # if the new cue is the same as the candidate cue, then increment the count of consecutive frames for the candidate cue
#                 count += 1
#                 if count >= CONFIRM_FRAMES: # if the count of consecutive frames for the candidate cue is at least CONFIRM_FRAMES, then switch to the candidate cue
#                     cue, count = new, 0
#             else:
#                 candidate, count = new, 1

#             # 5. tell the motor thread what to do
#             if cue == "STOP":
#                 pattern = (STOP_MOTORS, STOP_GAP)
#             elif cue == "LEFT":
#                 pattern = (LEFT_MOTORS, pulse_gap(smooth, box_h))   # if the cue is LEFT, then set the pattern to the left motors and the pulse gap based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             elif cue == "RIGHT":
#                 pattern = (RIGHT_MOTORS, pulse_gap(smooth, box_h))
#             elif cue == "BLOCKED":
#                 pattern = (STOP_MOTORS, pulse_gap(smooth, box_h))
#             else:
#                 pattern = ([], 0.0)
#             t4 = time.monotonic()

#             # # 6. timing printout every 30 frames
#             # for name, ms in (("camera", t1 - t0), ("depth", t2 - t1), ("yolo", t3 - t2), ("logic", t4 - t3)):# calculate the time taken for each step in milliseconds and add it to the timing dictionary
#             #     timing[name] += ms * 1000
#             # if frame_no % 30 == 0:  # every 30 frames, print the average timing for each step and the total time taken for all steps, as well as the frames per second (FPS) and the current cue
#             #     total = sum(timing.values()) / 30
#             #     print("TIMING (avg ms)  " + " | ".join(f"{k} {v / 30:.1f}" for k, v in timing.items())
#             #           + f" | total {total:.1f} | FPS {1000 / total:.1f} | cue {cue}")
#             #     timing = dict.fromkeys(timing, 0.0)

#             if cue != last_cue or frame_no % PRINT_EVERY == 0:
#                 obstacle = f"{box_label} (h {box_h:.2f})" if box_h >= YOLO_NEAR else "none"
#                 print(f"{cue:8s} | depth L {np.median(smooth[0:3]):.2f} C {np.median(smooth[2:5]):.2f}"
#                       f" R {np.median(smooth[4:7]):.2f}"
#                       f" | close L {np.mean(closeness(smooth[0:3])):.2f} R {np.mean(closeness(smooth[4:7])):.2f}"
#                       f" | urgency {get_urgency(smooth, box_h):.2f} | obstacle {obstacle}")
#                 last_cue = cue

#             # 7. log to CSV
#             if LOG:
#                 log.writerow([f"{time.time():.3f}", f"{(t4 - t0) * 1000:.3f}",  
#                               f"{np.mean(closeness(smooth[0:3])):.3f}", f"{np.median(smooth[2:5]):.3f}",
#                               f"{np.mean(closeness(smooth[4:7])):.3f}", cue,
#                               STRENGTH if cue != "CLEAR" else 0, int(box_h >= YOLO_NEAR),
#                               f"{box_h:.2f}", box_label])

#     except KeyboardInterrupt:
#         print("\nStopped.")
#     finally:
#         running = False                     # stop the motor thread...
#         if thread:
#             thread.join(timeout=1)
#         for drv in motors.values():         # ...then make sure every motor is off
#             try:
#                 drv.realtime_value = 0
#                 drv._write_u8(0x01, 0x40)   # standby: outputs fully off
#             except Exception:
#                 pass
#         if camera:
#             camera.stop()
#         if log_file:
#             log_file.close()
#         print("System stopped.")


# if __name__ == "__main__":
#     main()

































# # guide_minimal.py
# # ============================================================
# # MINIMAL GUIDE: the core idea, plus only the safeguards that fixed
# # real problems during testing. Read it top to bottom.
# #
# #   camera frame -> FastDepth -> 7 numbers -> if/else -> motors
# #
# #   Motors (wearer's view):  FRONT 6 7 2 0  /  BACK 4 5 3 1
# #     6, 4 = go LEFT     0, 1 = go RIGHT     3 = BLOCKED / STOP
# #     NEW: where BLOCKED is felt (or whether it exists) is set by BLOCKED_CUE
# #     nothing buzzing = path is clear
# #
# #   FastDepth numbers: LOWER = CLOSER (not real meters).
# # ============================================================

# import os # import os for directory creation and file handling
# import csv  #import csv for logging data in CSV format
# import time #import time for timing and sleep functions
# import signal   #import signal for handling termination signals
# import threading    #import threading for running the motor loop in a separate thread meaning the main loop can continue to run without being blocked by the motor loop

# import numpy as np
# import degirum as dg
# from picamera2 import Picamera2
# import board
# import busio
# import adafruit_tca9548a
# from adafruit_drv2605 import DRV2605, MODE_REALTIME


# # ---------------- SETTINGS ----------------
# #  Depth thresholds (meters) and other parameters
# AHEAD_DEPTH = 2.4      # your path reads closer than this -> guide
# STOP_DEPTH = 1.25      # your path reads closer than this -> STOP
# MAX_DEPTH = 2.5        # anything farther is ignored ("nothing close")
# SIDE_DIFF = 0.15       # how much more open a side must be to pick it (0-1 scale)
# SMOOTHING = 0.3        # weight of the newest frame: lower = steadier but slower
# CONFIRM_FRAMES = 3     # a new cue must repeat this many frames (STOP is instant)
# STOP_EXIT = 1.35       # NEW: once stopped, stay stopped until your path reads farther than this
# KEEP_SIDE = 0.075      # NEW: once turning, keep turning until the sides differ by less than this
# YOLO_PUSH = 0.6        # NEW: how strongly an off-center YOLO box pushes you to the other side
# YOLO_SIDE = 0.02       # NEW: with a YOLO obstacle ahead, even a small side difference picks a side

# USE_YOLO = False        # catch people/chairs that depth misses
# YOLO_NEAR = 0.40       # box at least this tall = NEAR (even if depth says clear)
# YOLO_STOP = 0.90       # box at least this tall = STOP (even if depth says clear)

# STRENGTH = 127                     # motor strength, 0-127
# PULSE_ON = 0.15                    # each pulse lasts this long (seconds)
# FAR_GAP, NEAR_GAP = 0.70, 0.10     # pause between pulses: far -> near
# STOP_GAP = 0.05                    # pause between STOP pulses (rapid)

# LEFT_MOTORS = [6, 4]
# RIGHT_MOTORS = [0, 1]
# STOP_MOTORS = [3]                  # motor 5 is broken, so only 3 for now
# FRONT_MOTORS = [7, 2]              # NEW: front center
# BLOCKED_CUE = "none"              # NEW: "front" = 7,2 | "back" = same motor as STOP | "none" = always pick a side until STOP
# BLOCKED_MOTORS = FRONT_MOTORS if BLOCKED_CUE == "front" else STOP_MOTORS   # NEW

# LOG = False             # CSV log in logs/ (works with compare_logs.py)
# PRINT_EVERY = 10       # status line every N frames (and whenever the cue changes)
# PRINT_TIMING = False   # True = also print how long each step takes (for speed comparisons)
# MODELS_DIR = "/home/rohan/degirum_wearable_device/models"
# YOLO_DIR = "/home/rohan/haptic feedback vest final/models"
# OBSTACLES = {"person", "chair", "bench", "couch", "backpack", "suitcase"}


# # ---------------- MOTORS ----------------
# # The main loop sets `pattern`; a small background thread does the pulsing,
# # so pulse timing stays steady even when a camera frame is slow.

# motors = {} # channel -> DRV2605 object
# pattern = ([], 0.0) # the current pattern: (active channels, gap between pulses)
# running = True  # whether the motor loop is running


# # ---------------- MOTOR HELPERS ----------------
# def connect_motor(ch):  # connect to a motor driver on the given TCA channel, return DRV2605 object
#     drv = DRV2605(tca[ch])  # connect to the DRV2605 driver on the given TCA channel
#     drv.mode = MODE_REALTIME  # "set the strength directly" mode
#     drv.realtime_value = 0  # start with the motor off
#     return drv  # return the DRV2605 object for the motor driver


# def set_motors(active, strength):   # set the given motors to the given strength, and turn off all others
#     for ch, drv in motors.items():  # iterate over all motors
#         try:
#             drv.realtime_value = strength if ch in active else 0    # set the strength of the motor to the given strength if it is in the active list, otherwise set it to 0 (off)
#         except Exception:
#             pass                   # a failed write is retried on the next pulse


# def wait(seconds, current):  # Check for a new pattern every 10ms, but don't block the motor thread for too long
#     end = time.monotonic() + seconds
#     while running and pattern == current and time.monotonic() < end:
#         time.sleep(0.01)


# def fix_reset_drivers():    # check all motor drivers and reconnect if needed
#     """A power dip resets a driver chip into standby, where it ignores us."""
#     for ch, drv in list(motors.items()):
#         try:
#             if drv.mode != MODE_REALTIME:   # if the driver is not in realtime mode, it has reset
#                 motors[ch] = connect_motor(ch)
#                 print(f"motor {ch} driver had reset (power dip) - restored")
#         except Exception:
#             pass


# def motor_loop():
#     last_check = time.monotonic()
#     while running:
#         current = pattern
#         active, gap = current
#         if active:
#             set_motors(active, STRENGTH)   # pulse on
#             wait(PULSE_ON, current)
#             set_motors([], 0)              # pulse off
#             wait(gap, current)
#         else:
#             set_motors([], 0)
#             wait(0.05, current)
#         if time.monotonic() - last_check > 1.0:   # once a second
#             fix_reset_drivers()
#             last_check = time.monotonic()


# # ---------------- DEPTH ---------------
# # Depth estimation from the camera frame
# def get_strips(frame):  #return 7 numbers (left to right) representing the median depth in each vertical strip of the frame, ignoring the ceiling and floor. The depth is scaled to meters using the quantization parameters from the model output.
#     out = depth_model.predict(frame)._inference_results[0]  # run the depth model on the frame and get the output
#     q = out["quantization"] # get the quantization parameters from the model output
#     depth = (out["data"].astype(np.float32) - q["zero"][0]) * q["scale"][0] # scale the output data to meters using the quantization parameters
#     depth = depth.reshape(224, 224) # reshape the output data to a 224x224 array
#     band = depth[56:179]               # rows 25%-80%: skip ceiling and the floor at your feet
#     return np.array([np.median(s) for s in np.array_split(band, 7, axis=1)])


# #A function that takes a depth value (in meters) and returns a closeness value between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). 
# def closeness(d):   
#     return np.clip((MAX_DEPTH - d) / (MAX_DEPTH - 0.5), 0, 1)   #clip the closeness value to be between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). The formula used is (MAX_DEPTH - d) / (MAX_DEPTH - 0.5), which scales the depth value to a closeness value between 0 and 1.


# # ---------------- THE DECISION (plain if/else) ----------------
# def decide(strips, box_h, box_x, cue):
#     ahead = np.median(strips[2:5])            # middle 3 strips = your path
#     left = np.mean(closeness(strips[0:3]))    # average closeness on the left
#     right = np.mean(closeness(strips[4:7]))   # average closeness on the right

#     stop_at = STOP_EXIT if cue == "STOP" else STOP_DEPTH   # NEW: already stopped -> stay stopped until clearly farther
#     if ahead <= stop_at or box_h >= YOLO_STOP:   # if the path ahead is too close or YOLO sees a very close obstacle, then stop
#         return "STOP"
#     if ahead >= AHEAD_DEPTH and box_h < YOLO_NEAR:  # if the path ahead is clear and YOLO does not see a close obstacle, then continue straight
#         return "CLEAR"

#     diff = left - right                       # NEW: > 0 means the left side has more close stuff
#     right_needed = KEEP_SIDE if cue == "RIGHT" else SIDE_DIFF   # NEW: already turning right -> easier to keep turning right
#     left_needed = KEEP_SIDE if cue == "LEFT" else SIDE_DIFF     # NEW: (switching sides still needs the full SIDE_DIFF)
#     if box_h >= YOLO_NEAR:                    # if YOLO sees a close obstacle, then turn away from it
#         diff += (0.5 - box_x) * YOLO_PUSH     # if the obstacle is on the left side, turn right; if it is on the right side, turn left
#         right_needed = min(right_needed, YOLO_SIDE)   # NEW: with a YOLO obstacle, any real difference picks a side
#         left_needed = min(left_needed, YOLO_SIDE)     # NEW
#     if diff >= right_needed:   # if the left side is significantly more open than the right side, then turn right
#         return "RIGHT"                        
#     if -diff >= left_needed:
#         return "LEFT"
#     if BLOCKED_CUE == "none":                 # NEW: no BLOCKED cue -> always point to a side until STOP
#         if cue in ("LEFT", "RIGHT"):          # NEW: already turning -> keep that direction
#             return cue
#         return "RIGHT" if diff > 0 else "LEFT"   # NEW: otherwise the (even slightly) more open side
#     return "BLOCKED"    # if the path is blocked and there is no clear direction to turn, then return "BLOCKED"


# def pulse_gap(strips, box_h):
#     """Closer obstacle -> shorter pause -> faster pulses (4 speeds)."""
#     ahead = np.median(strips[2:5])  # middle 3 strips = your path
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1) #assign urgency based on depth
#     if box_h >= YOLO_NEAR:  # YOLO sees someone in your way -> increase urgency
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))   # increase urgency based on box height
#     urgency = round(min(urgency, 1.0) * 3) / 3  # round to 0, 1/3, 2/3, 1
#     return FAR_GAP + (NEAR_GAP - FAR_GAP) * urgency # scale gap based on urgency


# def get_urgency(strips, box_h):   # NEW
#     """NEW: urgency for the status line: 0 = just noticed ... 1 = at STOP distance (same math as pulse_gap)."""
#     ahead = np.median(strips[2:5])
#     urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1)
#     if box_h >= YOLO_NEAR:
#         urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))
#     return float(min(urgency, 1.0))


# # ---------------- STOP SAFELY ----------------
# def stop_on_signal(signum, frame):
#     raise KeyboardInterrupt          # VS Code stop button / closed terminal -> normal shutdown


# signal.signal(signal.SIGTERM, stop_on_signal)
# signal.signal(signal.SIGHUP, stop_on_signal)


# # ---------------- MAIN ----------------
# def main():
#     global tca, depth_model, pattern, running
#     camera = thread = log_file = None
#     try:
#         print("Loading models...")
#         depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1",
#                                     "@local", MODELS_DIR)
#         yolo = None
#         if USE_YOLO:
#             yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
#                                  "@local", YOLO_DIR)
#             yolo.input_numpy_colorspace = "BGR"     # Pi camera frames are stored B,G,R

#         camera = Picamera2()
#         camera.configure(camera.create_preview_configuration(
#             main={"size": (640, 360), "format": "RGB888"}))
#         camera.start()
#         time.sleep(1.0)

#         tca = adafruit_tca9548a.TCA9548A(busio.I2C(board.SCL, board.SDA))
#         for ch in set(LEFT_MOTORS + RIGHT_MOTORS + STOP_MOTORS + BLOCKED_MOTORS):   # NEW: + BLOCKED_MOTORS
#             try:
#                 motors[ch] = connect_motor(ch)
#             except Exception as e:
#                 print(f"Motor {ch} unavailable: {e}")
#         thread = threading.Thread(target=motor_loop, daemon=True)
#         thread.start()

#         if LOG:
#             os.makedirs("logs", exist_ok=True)
#             log_file = open(f"logs/guide_minimal_{time.strftime('%Y%m%d_%H%M%S')}.csv",
#                             "w", newline="", buffering=1)
#             log = csv.writer(log_file)
#             log.writerow(["time", "frame_ms", "L", "C", "R", "state", "intensity", "yolo_near",
#                           "yolo_h", "yolo_label"])   # NEW: the last two columns

#         print("\nGUIDE MINIMAL running | Ctrl+C to quit\n")
#         smooth = None
#         cue, candidate, count = "CLEAR", None, 0    # the current cue, the candidate cue, and the count of consecutive frames for the candidate cue
#         box_h, box_x = 0.0, 0.5 # the height and x position of the tallest YOLO box in the middle third of the frame
#         box_label = ""          # the class of that box 
#         frame_no = 0    # the number of frames processed
#         last_cue = None # NEW: the cue printed last time (so we print whenever it changes)
#         timing = {"camera": 0.0, "depth": 0.0, "yolo": 0.0, "logic": 0.0}

#         while True:
#             t0 = time.monotonic()

#             # 1. camera
#             frame = camera.capture_array("main")
#             t1 = time.monotonic()

#             # 2. depth -> 7 numbers, smoothed over time
#             strips = get_strips(frame)
#             smooth = strips if smooth is None else SMOOTHING * strips + (1 - SMOOTHING) * smooth    # smooth the depth readings over time to reduce noise and fluctuations
#             t2 = time.monotonic()

#             # 3. YOLO (every 2nd frame to save time): tallest obstacle in the middle third
#             frame_no += 1
#             if yolo and frame_no % 2 == 0:  # run YOLO every 2nd frame to save time
#                 box_h, box_x = 0.0, 0.5 # reset the tallest box height and x position
#                 box_label = ""          # NEW
#                 for det in yolo.predict(frame).results:
#                     if det.get("label") in OBSTACLES and det.get("score", 0) >= 0.4:    # if the detected object is in the list of obstacles and the confidence score is at least 0.4
#                         x1, y1, x2, y2 = det["bbox"]    # get the bounding box coordinates of the detected object
#                         x, h = (x1 + x2) / 2 / 640, (y2 - y1) / 360  # calculate the center x position and height of the bounding box, normalized to the frame size
#                         if 0.33 <= x <= 0.67 and h > box_h:  # if the bounding box is in the middle third of the frame and taller than the previous tallest box, update the tallest box height and x position
#                             box_h, box_x = h, x
#                             box_label = det.get("label")   # NEW
#             t3 = time.monotonic()   # YOLO timing

#             # 4. decide, then only switch after CONFIRM_FRAMES agreeing frames
#             new = decide(smooth, box_h, box_x, cue)  # decide what to do based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             if new == "STOP" or new == cue: # if the new cue is STOP or the same as the current cue, then switch immediately
#                 cue, count = new, 0
#             elif new == candidate:  # if the new cue is the same as the candidate cue, then increment the count of consecutive frames for the candidate cue
#                 count += 1
#                 if count >= CONFIRM_FRAMES: # if the count of consecutive frames for the candidate cue is at least CONFIRM_FRAMES, then switch to the candidate cue
#                     cue, count = new, 0
#             else:
#                 candidate, count = new, 1

#             # 5. tell the motor thread what to do
#             if cue == "STOP":
#                 pattern = (STOP_MOTORS, STOP_GAP)
#             elif cue == "LEFT":
#                 pattern = (LEFT_MOTORS, pulse_gap(smooth, box_h))   # if the cue is LEFT, then set the pattern to the left motors and the pulse gap based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
#             elif cue == "RIGHT":
#                 pattern = (RIGHT_MOTORS, pulse_gap(smooth, box_h))
#             elif cue == "BLOCKED":
#                 pattern = (BLOCKED_MOTORS, pulse_gap(smooth, box_h))   # NEW: BLOCKED_MOTORS
#             else:
#                 pattern = ([], 0.0)
#             t4 = time.monotonic()

#             # # 6. timing printout every 30 frames
#             # for name, ms in (("camera", t1 - t0), ("depth", t2 - t1), ("yolo", t3 - t2), ("logic", t4 - t3)):# calculate the time taken for each step in milliseconds and add it to the timing dictionary
#             #     timing[name] += ms * 1000
#             # if frame_no % 30 == 0:  # every 30 frames, print the average timing for each step and the total time taken for all steps, as well as the frames per second (FPS) and the current cue
#             #     total = sum(timing.values()) / 30
#             #     print("TIMING (avg ms)  " + " | ".join(f"{k} {v / 30:.1f}" for k, v in timing.items())
#             #           + f" | total {total:.1f} | FPS {1000 / total:.1f} | cue {cue}")
#             #     timing = dict.fromkeys(timing, 0.0)

#             if cue != last_cue or frame_no % PRINT_EVERY == 0:
#                 obstacle = f"{box_label} (h {box_h:.2f})" if box_h >= YOLO_NEAR else "none"
#                 print(f"{cue:8s} | depth L {np.median(smooth[0:3]):.2f} C {np.median(smooth[2:5]):.2f}"
#                       f" R {np.median(smooth[4:7]):.2f}"
#                       f" | close L {np.mean(closeness(smooth[0:3])):.2f} R {np.mean(closeness(smooth[4:7])):.2f}"
#                       f" | urgency {get_urgency(smooth, box_h):.2f} | obstacle {obstacle}")
#                 last_cue = cue

#             # 7. log to CSV
#             if LOG:
#                 log.writerow([f"{time.time():.3f}", f"{(t4 - t0) * 1000:.3f}",  
#                               f"{np.mean(closeness(smooth[0:3])):.3f}", f"{np.median(smooth[2:5]):.3f}",
#                               f"{np.mean(closeness(smooth[4:7])):.3f}", cue,
#                               STRENGTH if cue != "CLEAR" else 0, int(box_h >= YOLO_NEAR),
#                               f"{box_h:.2f}", box_label])

#     except KeyboardInterrupt:
#         print("\nStopped.")
#     finally:
#         running = False                     # stop the motor thread...
#         if thread:
#             thread.join(timeout=1)
#         for drv in motors.values():         # ...then make sure every motor is off
#             try:
#                 drv.realtime_value = 0
#                 drv._write_u8(0x01, 0x40)   # standby: outputs fully off
#             except Exception:
#                 pass
#         if camera:
#             camera.stop()
#         if log_file:
#             log_file.close()
#         print("System stopped.")


# if __name__ == "__main__":
#     main()






































# guide_minimal.py
# ============================================================
# MINIMAL GUIDE: the core idea, plus only the safeguards that fixed
# real problems during testing. Read it top to bottom.
#
#   camera frame -> FastDepth -> 7 numbers -> if/else -> motors
#
#   Motors (wearer's view):  FRONT 6 7 2 0  /  BACK 4 5 3 1
#     6, 4 = go LEFT     0, 1 = go RIGHT     3 = BLOCKED / STOP
#     NEW: where BLOCKED is felt (or whether it exists) is set by BLOCKED_CUE
#     nothing buzzing = path is clear
#
#   FastDepth numbers: LOWER = CLOSER (not real meters).
# ============================================================

import os # import os for directory creation and file handling
import csv  #import csv for logging data in CSV format
import time #import time for timing and sleep functions
import signal   #import signal for handling termination signals
import threading    #import threading for running the motor loop in a separate thread meaning the main loop can continue to run without being blocked by the motor loop

import numpy as np
import cv2                   # NEW: only used for the optional preview window
import degirum as dg
from picamera2 import Picamera2
import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME


# ---------------- SETTINGS ----------------
#  Depth thresholds (meters) and other parameters
AHEAD_DEPTH = 2.4      # your path reads closer than this -> guide
STOP_DEPTH = 1.25      # your path reads closer than this -> STOP
MAX_DEPTH = 2.5        # anything farther is ignored ("nothing close")
SIDE_DIFF = 0.15       # how much more open a side must be to pick it (0-1 scale)
SMOOTHING = 0.3        # weight of the newest frame: lower = steadier but slower
CONFIRM_FRAMES = 3     # a new cue must repeat this many frames (STOP is instant)
STOP_EXIT = 1.35       # NEW: once stopped, stay stopped until your path reads farther than this
KEEP_SIDE = 0.075      # NEW: once turning, keep turning until the sides differ by less than this
YOLO_PUSH = 0.6        # NEW: how strongly an off-center YOLO box pushes you to the other side
YOLO_SIDE = 0.02       # NEW: with a YOLO obstacle ahead, even a small side difference picks a side

USE_YOLO = True        # catch people/chairs that depth misses
YOLO_NEAR = 0.40       # box at least this tall = NEAR (even if depth says clear)
YOLO_STOP = 0.90       # box at least this tall = STOP (even if depth says clear)

STRENGTH = 127                     # motor strength, 0-127
PULSE_ON = 0.15                    # each pulse lasts this long (seconds)
FAR_GAP, NEAR_GAP = 0.70, 0.10     # pause between pulses: far -> near
STOP_GAP = 0.05                    # pause between STOP pulses (rapid)

LEFT_MOTORS = [6, 4]
RIGHT_MOTORS = [0, 1]
STOP_MOTORS = [3]                  # motor 5 is broken, so only 3 for now
FRONT_MOTORS = [7, 2]              # NEW: front center
BLOCKED_CUE = "none"              # NEW: "front" = 7,2 | "back" = same motor as STOP | "none" = always pick a side until STOP
BLOCKED_MOTORS = FRONT_MOTORS if BLOCKED_CUE == "front" else STOP_MOTORS   # NEW

LOG = True             # CSV log in logs/ (works with compare_logs.py)
PRINT_EVERY = 10       # status line every N frames (and whenever the cue changes)
PRINT_TIMING = False   # True = also print how long each step takes (for speed comparisons)
SHOW_WINDOW = True    # NEW: True = preview window (for debugging; slows the loop a little)
SHOW_DEPTH = True      # NEW: with SHOW_WINDOW, also show the depth view next to the camera
PREVIEW_EVERY = 3      # NEW: redraw the window every N frames
MODELS_DIR = "/home/rohan/degirum_wearable_device/models"
YOLO_DIR = "/home/rohan/haptic feedback vest final/models"
OBSTACLES = {"person", "chair", "bench", "couch", "backpack", "suitcase"}


# ---------------- MOTORS ----------------
# The main loop sets `pattern`; a small background thread does the pulsing,
# so pulse timing stays steady even when a camera frame is slow.

motors = {} # channel -> DRV2605 object
pattern = ([], 0.0) # the current pattern: (active channels, gap between pulses)
running = True  # whether the motor loop is running


# ---------------- MOTOR HELPERS ----------------
def connect_motor(ch):  # connect to a motor driver on the given TCA channel, return DRV2605 object
    drv = DRV2605(tca[ch])  # connect to the DRV2605 driver on the given TCA channel
    drv.mode = MODE_REALTIME  # "set the strength directly" mode
    drv.realtime_value = 0  # start with the motor off
    return drv  # return the DRV2605 object for the motor driver


def set_motors(active, strength):   # set the given motors to the given strength, and turn off all others
    for ch, drv in motors.items():  # iterate over all motors
        try:
            drv.realtime_value = strength if ch in active else 0    # set the strength of the motor to the given strength if it is in the active list, otherwise set it to 0 (off)
        except Exception:
            pass                   # a failed write is retried on the next pulse


def wait(seconds, current):  # Check for a new pattern every 10ms, but don't block the motor thread for too long
    end = time.monotonic() + seconds
    while running and pattern == current and time.monotonic() < end:
        time.sleep(0.01)


def fix_reset_drivers():    # check all motor drivers and reconnect if needed
    """A power dip resets a driver chip into standby, where it ignores us."""
    for ch, drv in list(motors.items()):
        try:
            if drv.mode != MODE_REALTIME:   # if the driver is not in realtime mode, it has reset
                motors[ch] = connect_motor(ch)
                print(f"motor {ch} driver had reset (power dip) - restored")
        except Exception:
            pass


def motor_loop():
    last_check = time.monotonic()
    while running:
        current = pattern
        active, gap = current
        if active:
            set_motors(active, STRENGTH)   # pulse on
            wait(PULSE_ON, current)
            set_motors([], 0)              # pulse off
            wait(gap, current)
        else:
            set_motors([], 0)
            wait(0.05, current)
        if time.monotonic() - last_check > 1.0:   # once a second
            fix_reset_drivers()
            last_check = time.monotonic()


# ---------------- DEPTH ---------------
# Depth estimation from the camera frame
def get_strips(frame):  #return 7 numbers (left to right) representing the median depth in each vertical strip of the frame, ignoring the ceiling and floor. The depth is scaled to meters using the quantization parameters from the model output.
    out = depth_model.predict(frame)._inference_results[0]  # run the depth model on the frame and get the output
    q = out["quantization"] # get the quantization parameters from the model output
    depth = (out["data"].astype(np.float32) - q["zero"][0]) * q["scale"][0] # scale the output data to meters using the quantization parameters
    depth = depth.reshape(224, 224) # reshape the output data to a 224x224 array
    global last_depth                  # NEW: keep the full map for the preview window
    last_depth = depth                 # NEW
    band = depth[56:179]               # rows 25%-80%: skip ceiling and the floor at your feet
    return np.array([np.median(s) for s in np.array_split(band, 7, axis=1)])


#A function that takes a depth value (in meters) and returns a closeness value between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). 
def closeness(d):   
    return np.clip((MAX_DEPTH - d) / (MAX_DEPTH - 0.5), 0, 1)   #clip the closeness value to be between 0 and 1, where 0 means nothing is close (MAX_DEPTH or farther) and 1 means something is very close (0.5 meters). The formula used is (MAX_DEPTH - d) / (MAX_DEPTH - 0.5), which scales the depth value to a closeness value between 0 and 1.


# ---------------- THE DECISION (plain if/else) ----------------
def decide(strips, box_h, box_x, cue):
    ahead = np.median(strips[2:5])            # middle 3 strips = your path
    left = np.mean(closeness(strips[0:3]))    # average closeness on the left
    right = np.mean(closeness(strips[4:7]))   # average closeness on the right

    stop_at = STOP_EXIT if cue == "STOP" else STOP_DEPTH   # NEW: already stopped -> stay stopped until clearly farther
    if ahead <= stop_at or box_h >= YOLO_STOP:   # if the path ahead is too close or YOLO sees a very close obstacle, then stop
        return "STOP"
    if ahead >= AHEAD_DEPTH and box_h < YOLO_NEAR:  # if the path ahead is clear and YOLO does not see a close obstacle, then continue straight
        return "CLEAR"

    diff = left - right                       # NEW: > 0 means the left side has more close stuff
    right_needed = KEEP_SIDE if cue == "RIGHT" else SIDE_DIFF   # NEW: already turning right -> easier to keep turning right
    left_needed = KEEP_SIDE if cue == "LEFT" else SIDE_DIFF     # NEW: (switching sides still needs the full SIDE_DIFF)
    if box_h >= YOLO_NEAR:                    # if YOLO sees a close obstacle, then turn away from it
        diff += (0.5 - box_x) * YOLO_PUSH     # if the obstacle is on the left side, turn right; if it is on the right side, turn left
        right_needed = min(right_needed, YOLO_SIDE)   # NEW: with a YOLO obstacle, any real difference picks a side
        left_needed = min(left_needed, YOLO_SIDE)     # NEW
    if diff >= right_needed:   # if the left side is significantly more open than the right side, then turn right
        return "RIGHT"                        
    if -diff >= left_needed:
        return "LEFT"
    if BLOCKED_CUE == "none":                 # NEW: no BLOCKED cue -> always point to a side until STOP
        if cue in ("LEFT", "RIGHT"):          # NEW: already turning -> keep that direction
            return cue
        return "RIGHT" if diff > 0 else "LEFT"   # NEW: otherwise the (even slightly) more open side
    return "BLOCKED"    # if the path is blocked and there is no clear direction to turn, then return "BLOCKED"


def pulse_gap(strips, box_h):
    """Closer obstacle -> shorter pause -> faster pulses (4 speeds)."""
    ahead = np.median(strips[2:5])  # middle 3 strips = your path
    urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1) #assign urgency based on depth
    if box_h >= YOLO_NEAR:  # YOLO sees someone in your way -> increase urgency
        urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))   # increase urgency based on box height
    urgency = round(min(urgency, 1.0) * 3) / 3  # round to 0, 1/3, 2/3, 1
    return FAR_GAP + (NEAR_GAP - FAR_GAP) * urgency # scale gap based on urgency


def get_urgency(strips, box_h):   # NEW
    """NEW: urgency for the status line: 0 = just noticed ... 1 = at STOP distance (same math as pulse_gap)."""
    ahead = np.median(strips[2:5])
    urgency = np.clip((MAX_DEPTH - ahead) / (MAX_DEPTH - STOP_DEPTH), 0, 1)
    if box_h >= YOLO_NEAR:
        urgency = max(urgency, (box_h - YOLO_NEAR) / (YOLO_STOP - YOLO_NEAR))
    return float(min(urgency, 1.0))


# ---------------- PREVIEW (NEW, optional) ----------------
last_depth = None   # NEW: full depth map from the latest frame


def draw_preview(frame, strips, cue, box_label, box_h):   # NEW
    """NEW: camera (+ depth) with the 7 strips, their values and the current cue."""
    h, w = frame.shape[:2]
    views = [frame.copy()]
    if SHOW_DEPTH and last_depth is not None:
        close_map = closeness(last_depth)                 # red = close, blue = far (fixed scale)
        color = cv2.applyColorMap((close_map * 255).astype(np.uint8), cv2.COLORMAP_JET)
        views.append(cv2.resize(color, (w, h), interpolation=cv2.INTER_NEAREST))
    y1, y2, sw = int(h * 0.25), int(h * 0.80), w / 7      # the band and strips actually used
    for view in views:
        cv2.line(view, (0, y1), (w, y1), (255, 255, 255), 1)
        cv2.line(view, (0, y2), (w, y2), (255, 255, 255), 1)
        for i in range(1, 7):
            cv2.line(view, (int(i * sw), y1), (int(i * sw), y2), (255, 255, 255), 1)
        for i, d in enumerate(strips):                    # yellow = close enough to matter
            col = (0, 255, 255) if closeness(d) > 0 else (255, 255, 255)
            cv2.putText(view, f"{d:.1f}", (int(i * sw) + 4, y1 + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
    obstacle = f"  {box_label} h {box_h:.2f}" if box_h >= YOLO_NEAR else ""
    cv2.putText(views[0], f"{cue}{obstacle}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    if len(views) > 1:
        cv2.putText(views[1], "DEPTH  red = close, blue = far", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return np.hstack(views)


# ---------------- STOP SAFELY ----------------
def stop_on_signal(signum, frame):
    raise KeyboardInterrupt          # VS Code stop button / closed terminal -> normal shutdown


signal.signal(signal.SIGTERM, stop_on_signal)
signal.signal(signal.SIGHUP, stop_on_signal)


# ---------------- MAIN ----------------
def main():
    global tca, depth_model, pattern, running
    camera = thread = log_file = None
    try:
        print("Loading models...")
        depth_model = dg.load_model("fastdepth--224x224_quant_hailort_hailo8_1",
                                    "@local", MODELS_DIR)
        yolo = None
        if USE_YOLO:
            yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
                                 "@local", YOLO_DIR)
            yolo.input_numpy_colorspace = "BGR"     # Pi camera frames are stored B,G,R

        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(
            main={"size": (640, 360), "format": "RGB888"}))
        camera.start()
        time.sleep(1.0)

        tca = adafruit_tca9548a.TCA9548A(busio.I2C(board.SCL, board.SDA))
        for ch in set(LEFT_MOTORS + RIGHT_MOTORS + STOP_MOTORS + BLOCKED_MOTORS):   # NEW: + BLOCKED_MOTORS
            try:
                motors[ch] = connect_motor(ch)
            except Exception as e:
                print(f"Motor {ch} unavailable: {e}")
        thread = threading.Thread(target=motor_loop, daemon=True)
        thread.start()

        if LOG:
            os.makedirs("logs", exist_ok=True)
            log_file = open(f"logs/guide_minimal_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                            "w", newline="", buffering=1)
            log = csv.writer(log_file)
            log.writerow(["time", "frame_ms", "L", "C", "R", "state", "intensity", "yolo_near",
                          "yolo_h", "yolo_label"])   # NEW: the last two columns

        print("\nGUIDE MINIMAL running | Ctrl+C to quit\n")
        smooth = None
        cue, candidate, count = "CLEAR", None, 0    # the current cue, the candidate cue, and the count of consecutive frames for the candidate cue
        box_h, box_x = 0.0, 0.5 # the height and x position of the tallest YOLO box in the middle third of the frame
        box_label = ""          # the class of that box 
        frame_no = 0    # the number of frames processed
        last_cue = None # NEW: the cue printed last time (so we print whenever it changes)
        timing = {"camera": 0.0, "depth": 0.0, "yolo": 0.0, "logic": 0.0}

        while True:
            t0 = time.monotonic()

            # 1. camera
            frame = camera.capture_array("main")
            t1 = time.monotonic()

            # 2. depth -> 7 numbers, smoothed over time
            strips = get_strips(frame)
            smooth = strips if smooth is None else SMOOTHING * strips + (1 - SMOOTHING) * smooth    # smooth the depth readings over time to reduce noise and fluctuations
            t2 = time.monotonic()

            # 3. YOLO (every 2nd frame to save time): tallest obstacle in the middle third
            frame_no += 1
            if yolo and frame_no % 2 == 0:  # run YOLO every 2nd frame to save time
                box_h, box_x = 0.0, 0.5 # reset the tallest box height and x position
                box_label = ""          # NEW
                for det in yolo.predict(frame).results:
                    if det.get("label") in OBSTACLES and det.get("score", 0) >= 0.4:    # if the detected object is in the list of obstacles and the confidence score is at least 0.4
                        x1, y1, x2, y2 = det["bbox"]    # get the bounding box coordinates of the detected object
                        x, h = (x1 + x2) / 2 / 640, (y2 - y1) / 360  # calculate the center x position and height of the bounding box, normalized to the frame size
                        if 0.33 <= x <= 0.67 and h > box_h:  # if the bounding box is in the middle third of the frame and taller than the previous tallest box, update the tallest box height and x position
                            box_h, box_x = h, x
                            box_label = det.get("label")   # NEW
            t3 = time.monotonic()   # YOLO timing

            # 4. decide, then only switch after CONFIRM_FRAMES agreeing frames
            new = decide(smooth, box_h, box_x, cue)  # decide what to do based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
            if new == "STOP" or new == cue: # if the new cue is STOP or the same as the current cue, then switch immediately
                cue, count = new, 0
            elif new == candidate:  # if the new cue is the same as the candidate cue, then increment the count of consecutive frames for the candidate cue
                count += 1
                if count >= CONFIRM_FRAMES: # if the count of consecutive frames for the candidate cue is at least CONFIRM_FRAMES, then switch to the candidate cue
                    cue, count = new, 0
            else:
                candidate, count = new, 1

            # 5. tell the motor thread what to do
            if cue == "STOP":
                pattern = (STOP_MOTORS, STOP_GAP)
            elif cue == "LEFT":
                pattern = (LEFT_MOTORS, pulse_gap(smooth, box_h))   # if the cue is LEFT, then set the pattern to the left motors and the pulse gap based on the smoothed depth readings and the tallest YOLO box in the middle third of the frame
            elif cue == "RIGHT":
                pattern = (RIGHT_MOTORS, pulse_gap(smooth, box_h))
            elif cue == "BLOCKED":
                pattern = (BLOCKED_MOTORS, pulse_gap(smooth, box_h))   # NEW: BLOCKED_MOTORS
            else:
                pattern = ([], 0.0)
            t4 = time.monotonic()

            # # 6. timing printout every 30 frames
            # for name, ms in (("camera", t1 - t0), ("depth", t2 - t1), ("yolo", t3 - t2), ("logic", t4 - t3)):# calculate the time taken for each step in milliseconds and add it to the timing dictionary
            #     timing[name] += ms * 1000
            # if frame_no % 30 == 0:  # every 30 frames, print the average timing for each step and the total time taken for all steps, as well as the frames per second (FPS) and the current cue
            #     total = sum(timing.values()) / 30
            #     print("TIMING (avg ms)  " + " | ".join(f"{k} {v / 30:.1f}" for k, v in timing.items())
            #           + f" | total {total:.1f} | FPS {1000 / total:.1f} | cue {cue}")
            #     timing = dict.fromkeys(timing, 0.0)

            if cue != last_cue or frame_no % PRINT_EVERY == 0:
                obstacle = f"{box_label} (h {box_h:.2f})" if box_h >= YOLO_NEAR else "none"
                print(f"{cue:8s} | depth L {np.median(smooth[0:3]):.2f} C {np.median(smooth[2:5]):.2f}"
                      f" R {np.median(smooth[4:7]):.2f}"
                      f" | close L {np.mean(closeness(smooth[0:3])):.2f} R {np.mean(closeness(smooth[4:7])):.2f}"
                      f" | urgency {get_urgency(smooth, box_h):.2f} | obstacle {obstacle}")
                last_cue = cue

            # NEW: optional preview window
            if SHOW_WINDOW and frame_no % PREVIEW_EVERY == 0:
                cv2.imshow("Guide minimal", draw_preview(frame, smooth, cue, box_label, box_h))
                if cv2.waitKey(1) & 0xFF == ord("q"):   # NEW: press q in the window to quit
                    break

            # 7. log to CSV
            if LOG:
                log.writerow([f"{time.time():.3f}", f"{(t4 - t0) * 1000:.3f}",  
                              f"{np.mean(closeness(smooth[0:3])):.3f}", f"{np.median(smooth[2:5]):.3f}",
                              f"{np.mean(closeness(smooth[4:7])):.3f}", cue,
                              STRENGTH if cue != "CLEAR" else 0, int(box_h >= YOLO_NEAR),
                              f"{box_h:.2f}", box_label])

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        running = False                     # stop the motor thread...
        if thread:
            thread.join(timeout=1)
        for drv in motors.values():         # ...then make sure every motor is off
            try:
                drv.realtime_value = 0
                drv._write_u8(0x01, 0x40)   # standby: outputs fully off
            except Exception:
                pass
        if camera:
            camera.stop()
        if log_file:
            log_file.close()
        if SHOW_WINDOW:
            cv2.destroyAllWindows()   # NEW
        print("System stopped.")


if __name__ == "__main__":
    main()