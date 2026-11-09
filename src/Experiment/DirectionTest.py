# =========================================================
# PHASE 2 DIRECTION TEST SCRIPT
#
# Strategies:
#   Static:   90
#   Sweep:    sweep 90
#   Weighted: weighted 90
#
# Newest Version adding more distinction between front, diagonal, and sides by slightly changing motor assignments and placement of front and back
# =========================================================

import time
import atexit
import signal
import sys

import board
import busio
import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, Effect, MODE_REALTIME


# =========================================================
# PHYSICAL MOTOR MAP
# =========================================================
# This is the physical layout of the motors on the vest. The numbers correspond to the motor channels.
# FRONT ROW: 6   7   2   0
# BACK ROW:  4   5   3   1

FRONT = [7, 2]
FRONT_RIGHT = [0]
RIGHT = [ 0, 1]
BACK_RIGHT = [ 1]
BACK = [5, 3]
BACK_LEFT = [4]
LEFT = [6, 4]
FRONT_LEFT = [6]

DRIVERS = {}    # Dictionary to hold DRV2605 driver instances for each motor channel

MAX_INTENSITY = 200  # Maximum intensity for motor vibrations

# DRV2605 library effects
STRONG_INTENSITY = 200
WEAK_INTENSITY = 50


# =========================================================
# INITIALIZATION
# =========================================================

def init_motors():
    print("[SYSTEM] Initializing motors...")

    # Initialize I2C bus for communication with the TCA9548A multiplexer
    i2c = busio.I2C(board.SCL, board.SDA)
    # Create an instance of the TCA9548A multiplexer to manage multiple I2C devices on different channels
    mux = adafruit_tca9548a.TCA9548A(i2c)

    success = 0

    for i in range(8):  # Loop through motor channels 0 to 7
        try:
            drv = DRV2605(mux[i])
            # Set the driver to realtime mode for direct control of vibration intensity
            drv.mode = MODE_REALTIME
            drv.realtime_value = 0
            # Store the driver instance in the DRIVERS dictionary for later use
            DRIVERS[i] = drv
            print(f"[OK] Motor {i} connected")
            success += 1

        except Exception as e:
            DRIVERS[i] = None
            print(f"[ERROR] Motor {i}: {e}")

    return success > 0


# =========================================================
# BASIC MOTOR CONTROL
# =========================================================

def motor_on(channel, intensity=MAX_INTENSITY):
    if DRIVERS.get(channel):
        DRIVERS[channel].mode = MODE_REALTIME
        # Set the vibration intensity for the specified motor channel
        DRIVERS[channel].realtime_value = intensity


def all_off():
    for drv in DRIVERS.values():
        if drv:
            drv.realtime_value = 0


def play_effect(channel, effect_id):
    """
    Plays a DRV2605 library effect on one motor.
    """
    drv = DRIVERS.get(channel)

    if drv:     # Only works if the motor was successfully initialized
        drv.sequence[0] = Effect(effect_id)
        drv.sequence[1] = Effect(0)
        drv.play()


# =========================================================
# CLEAN SHUTDOWN
# =========================================================

def shutdown():
    all_off()
    print("\n[SYSTEM] Motors safely turned off.")


def handle_exit(sig, frame):
    shutdown()
    sys.exit(0)


atexit.register(shutdown)
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


# =========================================================
# SHARED LOGIC
# =========================================================

def normalize_degree(deg):  # Ensure degree is between 0 and 360
    return deg % 360


# DIRECTION GROUPS
def degree_to_direction_group(degree):
    degree = normalize_degree(degree)

    if degree >= 337.5 or degree < 22.5:
        return "FRONT", FRONT

    elif 22.5 <= degree < 67.5:
        return "FRONT RIGHT", FRONT_RIGHT

    elif 67.5 <= degree < 112.5:
        return "RIGHT", RIGHT

    elif 112.5 <= degree < 157.5:
        return "BACK RIGHT", BACK_RIGHT

    elif 157.5 <= degree < 202.5:
        return "BACK", BACK

    elif 202.5 <= degree < 247.5:
        return "BACK LEFT", BACK_LEFT

    elif 247.5 <= degree < 292.5:
        return "LEFT", LEFT

    elif 292.5 <= degree < 337.5:
        return "FRONT LEFT", FRONT_LEFT

# NEIGHBORING DIRECTIONS FOR WEIGHTED CUES


def degree_to_neighbors(degree):
    degree = normalize_degree(degree)

    if degree >= 337.5 or degree < 22.5:
        return [FRONT_LEFT, FRONT_RIGHT]

    elif 22.5 <= degree < 67.5:
        return [FRONT, RIGHT]

    elif 67.5 <= degree < 112.5:
        return [FRONT_RIGHT, BACK_RIGHT]

    elif 112.5 <= degree < 157.5:
        return [RIGHT, BACK]

    elif 157.5 <= degree < 202.5:
        return [BACK_RIGHT, BACK_LEFT]

    elif 202.5 <= degree < 247.5:
        return [BACK, LEFT]

    elif 247.5 <= degree < 292.5:
        return [BACK_LEFT, FRONT_LEFT]

    elif 292.5 <= degree < 337.5:
        return [LEFT, FRONT]


# =========================================================
# STRATEGY 1: STATIC SPATIAL ACTIVATION
# =========================================================

# Pulses all motors in the group simultaneously for a number of repeats
def pulse_group(group, repeats=2, intensity=150, on_time=0.30, off_time=0.05):
    for _ in range(repeats):
        for motor in group:
            motor_on(motor, intensity)

        time.sleep(on_time)
        all_off()
        time.sleep(off_time)


# Pulses the motors corresponding to the target direction simultaneously for a number of repeats
def static_to_degree(degree):
    degree = normalize_degree(degree)
    name, group = degree_to_direction_group(degree)

    print(f"\n[STATIC] {degree}° = {name}")
    pulse_group(group, repeats=2, intensity=127)
    all_off()


# # =========================================================
# # STRATEGY 2: SEQUENTIAL SWEEP WHERE INTENSITY INCREASES TOWARD TARGET
# # =========================================================

def sweep_groups(path, start_intensity=100, end_intensity=200,
                 beep_on=0.30, beep_off=0.05,
                 beeps_per_group=1, group_gap=0.15):

    num_steps = len(path)

    # Calculate the intensity for each step in the sweep based on its position in the path
    for i, group in enumerate(path):
        if num_steps == 1:
            intensity = end_intensity
        else:
            intensity = int(
                start_intensity
                + i * (end_intensity - start_intensity) / (num_steps - 1)
            )

        print(f"[SWEEP STEP] Motors: {group} | Intensity: {intensity}")

        for _ in range(beeps_per_group):
            all_off()

            for motor in group:
                motor_on(motor, intensity)

            time.sleep(beep_on)
            all_off()
            time.sleep(beep_off)

        time.sleep(group_gap)

# ASSIGNMENT OF DIRECTION GROUPS TO SWEEP PATHS BASED ON ANGLE


def sweep_to_degree(degree):

    degree = normalize_degree(degree)

    if degree >= 337.5 or degree < 22.5:
        path = [FRONT]

    elif 22.5 <= degree < 67.5:
        path = [FRONT, FRONT_RIGHT]

    elif 67.5 <= degree < 112.5:
        path = [FRONT, FRONT_RIGHT, RIGHT]

    elif 112.5 <= degree < 157.5:
        path = [FRONT, FRONT_RIGHT, RIGHT, BACK_RIGHT]

    elif 157.5 <= degree < 202.5:
        path = [FRONT, FRONT_RIGHT, RIGHT, BACK_RIGHT, BACK]

    elif 202.5 <= degree < 247.5:
        path = [FRONT, FRONT_LEFT, LEFT, BACK_LEFT]

    elif 247.5 <= degree < 292.5:
        path = [FRONT, FRONT_LEFT, LEFT]

    elif 292.5 <= degree < 337.5:
        path = [FRONT, FRONT_LEFT]

    name, final_group = degree_to_direction_group(degree)

    print(f"\n[SWEEP] {degree}° = {name}")

    sweep_groups(
        path,
        start_intensity=100,  # THE INITIAL INTENSITY FOR THE SWEEP
        end_intensity=200,  # THE FINAL INTENSITY FOR THE TARGET DIRECTION
        beep_on=0.30,   # THE TIME THE MOTOR IS ON DURING EACH PULSE, SHORTER ON TIME FOR A QUICKER SENSATION
        beep_off=0.05,  # THE TIME THE MOTOR IS OFF BETWEEN PULSES, SHORTER OFF TIME FOR A MORE CONTINUOUS SENSATION
        beeps_per_group=1,  # NUMBER OF PULSES PER GROUP, SINGLE PULSE FOR A CLEANER SWEEP
        group_gap=0.15  # THE TIME BETWEEN GROUPS, SHORTER GAP FOR A FASTER SWEEP
    )

    # Final confirmation pulse on the target direction
    # pulse_group(
    #     final_group,
    #     repeats=1,
    #     intensity=160,
    #     on_time=0.25,
    #     off_time=0.05
    # )

    all_off()


# =========================================================
# STRATEGY 3: INTENSITY-WEIGHTED ACTIVATION WHERE TARGET DIRECTION IS STRONGEST AND NEIGHBORS ARE WEAKER
# =========================================================

def weighted_to_degree(degree, repeats=2):

    degree = normalize_degree(degree)

    name, primary_group = degree_to_direction_group(degree)
    neighbor_groups = degree_to_neighbors(degree)

    print(f"\n[WEIGHTED] {degree}° = {name}")

    for _ in range(repeats):

        # Turn off everything first
        all_off()

        # Weak neighbors
        for group in neighbor_groups:
            for motor in group:
                if motor not in primary_group:
                    motor_on(motor, WEAK_INTENSITY)

        # Strong target motors
        for motor in primary_group:
            motor_on(motor, STRONG_INTENSITY)

        # Hold combined cue
        time.sleep(0.35)

        all_off()
        time.sleep(0.20)

    all_off()
# =========================================================
# 360 DEGREE TEST FUNCTIONS FOR EVERY STRATEGY AND INDIVIDUAL MOTORS
# =========================================================


def test_each_motor():
    for i in range(8):
        print(f"\n[TEST] Motor {i}")
        pulse_group([i], repeats=1, intensity=127, on_time=0.25)
        time.sleep(0.8)


def static_test():
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        static_to_degree(angle)
        time.sleep(0.8)


def sweep_test():
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        sweep_to_degree(angle)
        time.sleep(0.8)


def weighted_test():
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        weighted_to_degree(angle, repeats=3)
        time.sleep(0.8)

# =========================================================
# MAIN
# =========================================================


def main():
    if not init_motors():
        print("[ERROR] Could not initialize motors.")
        return

    print("\n===================================")
    print("PHASE 2 DIRECTION TEST")
    print("===================================")
    print("Static cue:")
    print("  90")
    print("Sweep cue:")
    print("  s 90")
    print("Weighted cue:")
    print("  w 90")
    print("-----------------------------------")
    print("Directions:")
    print("  0   = Front")
    print("  45  = Front Right")
    print("  90  = Right")
    print("  180 = Back")
    print("  270 = Left")
    print("  315 = Front Left")
    print("-----------------------------------")
    print("Commands:")
    print("  m")
    print("  statictest")
    print("  sweeptest")
    print("  weightedtest")
    print("  q")
    print("===================================")

    while True:
        user_input = input("\nEnter command: ").strip().lower()

        if user_input == "q":
            break

        elif user_input == "m":
            test_each_motor()

        elif user_input == "statictest":
            static_test()

        elif user_input == "sweeptest":
            sweep_test()

        elif user_input == "weightedtest":
            weighted_test()

        elif user_input.startswith("s"):
            try:
                parts = user_input.split()
                deg = float(parts[1])
                sweep_to_degree(deg)
            except:
                print("[ERROR] Use format: s 90")

        elif user_input.startswith("w"):
            try:
                parts = user_input.split()
                deg = float(parts[1])
                weighted_to_degree(deg, repeats=3)

            except IndexError:
                print("[ERROR] Use format: w 90")

            except Exception as e:
                print(f"[ERROR] {e}")
        else:
            try:
                deg = float(user_input)
                static_to_degree(deg)
            except:
                print("[ERROR] Invalid command.")

    all_off()


if __name__ == "__main__":
    main()
