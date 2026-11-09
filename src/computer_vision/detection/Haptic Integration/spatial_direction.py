# =========================================================
# TRUE 360 DEGREE HAPTIC NAVIGATION SYSTEM
# Based on YOUR exact actuator layout
# =========================================================

import time
import atexit
import signal
import board
import busio
import adafruit_tca9548a

from adafruit_drv2605 import DRV2605, MODE_REALTIME

# =========================================================
# MOTOR LAYOUT
# =========================================================

"""
FRONT VIEW

Right Side          Left Side
0   2               3   6


BACK VIEW

Left Side           Right Side
4   5               1   7
"""

# Clockwise order around body
CLOCKWISE_RING = [0, 2, 3, 6, 7, 1, 5, 4]

# Counter-clockwise
COUNTER_CLOCKWISE_RING = [4, 5, 1, 7, 6, 3, 2, 0]

DRIVERS = {}

MAX_INTENSITY = 127

PULSE_TIME = 0.12
GAP_TIME = 0.04

# =========================================================
# INITIALIZATION
# =========================================================

def init_motors():

    print("[SYSTEM] Initializing motors...")

    i2c = busio.I2C(board.SCL, board.SDA)

    mux = adafruit_tca9548a.TCA9548A(i2c)

    success = 0

    for i in range(8):

        try:
            drv = DRV2605(mux[i])

            drv.mode = MODE_REALTIME
            drv.realtime_value = 0

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

    if DRIVERS[channel]:
        DRIVERS[channel].realtime_value = intensity


def motor_off(channel):

    if DRIVERS[channel]:
        DRIVERS[channel].realtime_value = 0


def all_off():

    for drv in DRIVERS.values():

        if drv:
            drv.realtime_value = 0

# =========================================================
# CLEAN SHUTDOWN
# =========================================================

def shutdown():

    all_off()

    print("\n[SYSTEM] Motors safely turned off.")

atexit.register(shutdown)

signal.signal(signal.SIGINT, lambda s, f: exit())

# =========================================================
# WAVE EFFECTS
# =========================================================

def wave_clockwise(speed=0.12, intensity=110, loops=2):

    for _ in range(loops):

        for motor in CLOCKWISE_RING:

            all_off()

            motor_on(motor, intensity)

            time.sleep(speed)

            motor_off(motor)

            time.sleep(GAP_TIME)


def wave_counterclockwise(speed=0.12, intensity=110, loops=2):

    for _ in range(loops):

        for motor in COUNTER_CLOCKWISE_RING:

            all_off()

            motor_on(motor, intensity)

            time.sleep(speed)

            motor_off(motor)

            time.sleep(GAP_TIME)


def pulse_group(group, repeats=4, intensity=115):

    for _ in range(repeats):

        for m in group:
            motor_on(m, intensity)

        time.sleep(0.2)

        all_off()

        time.sleep(0.08)

# =========================================================
# DEGREE NAVIGATION
# =========================================================

def normalize_degree(deg):

    return deg % 360

# =========================================================
# MAIN NAVIGATION LOGIC
# =========================================================

def navigate_to_degree(degree):

    degree = normalize_degree(degree)

    print(f"\n[NAVIGATION] Target Direction: {degree}°")

    # =====================================================
    # FRONT
    # =====================================================

    if degree >= 337.5 or degree < 22.5:

        print("Direction = FRONT")

        pulse_group([0, 2, 3, 6], repeats=5)

    # =====================================================
    # FRONT RIGHT
    # =====================================================

    elif 22.5 <= degree < 67.5:

        print("Direction = FRONT RIGHT")

        pulse_group([0, 2], repeats=5)

    # =====================================================
    # RIGHT
    # =====================================================

    elif 67.5 <= degree < 112.5:

        print("Direction = RIGHT")

        wave_clockwise(speed=0.10, loops=3)

    # =====================================================
    # BACK RIGHT
    # =====================================================

    elif 112.5 <= degree < 157.5:

        print("Direction = BACK RIGHT")

        pulse_group([7, 1], repeats=5)

    # =====================================================
    # BACK
    # =====================================================

    elif 157.5 <= degree < 202.5:

        print("Direction = BACK")

        # Full circular warning
        wave_clockwise(speed=0.07, loops=4)

    # =====================================================
    # BACK LEFT
    # =====================================================

    elif 202.5 <= degree < 247.5:

        print("Direction = BACK LEFT")

        pulse_group([4, 5], repeats=5)

    # =====================================================
    # LEFT
    # =====================================================

    elif 247.5 <= degree < 292.5:

        print("Direction = LEFT")

        wave_counterclockwise(speed=0.10, loops=3)

    # =====================================================
    # FRONT LEFT
    # =====================================================

    elif 292.5 <= degree < 337.5:

        print("Direction = FRONT LEFT")

        pulse_group([3, 6], repeats=5)

    all_off()

# =========================================================
# TEST ALL DIRECTIONS
# =========================================================

def full_360_test():

    test_angles = [
        0,
        45,
        90,
        135,
        180,
        225,
        270,
        315
    ]

    for angle in test_angles:

        navigate_to_degree(angle)

        time.sleep(1)

# =========================================================
# MAIN
# =========================================================

def main():

    if not init_motors():

        print("[ERROR] Could not initialize motors.")

        return

    print("\n===================================")
    print("TRUE 360 HAPTIC NAVIGATION SYSTEM")
    print("===================================")
    print("Enter ANY degree 0-359")
    print("0 = FRONT")
    print("90 = RIGHT")
    print("180 = BACK")
    print("270 = LEFT")
    print("===================================")

    while True:

        user_input = input("\nEnter Degree (or 'test' / 'q'): ").strip().lower()

        if user_input == 'q':

            break

        elif user_input == 'test':

            full_360_test()

        else:

            try:

                deg = float(user_input)

                navigate_to_degree(deg)

            except:

                print("[ERROR] Invalid Input")

    all_off()

# =========================================================

if __name__ == "__main__":

    main()