# =========================================================
# UPDATED 360 DEGREE HAPTIC NAVIGATION SYSTEM
# Based on CURRENT physical actuator placement
#
# FRONT ROW: 6   7   2   0
# BACK ROW:  4   5   3   1
# =========================================================

import time
import atexit
import signal
import board
import busio
import adafruit_tca9548a

from adafruit_drv2605 import DRV2605, MODE_REALTIME

# =========================================================
# REAL PHYSICAL MOTOR MAP
# =========================================================

FRONT = [7, 2]
FRONT_RIGHT = [2, 0]
RIGHT = [0, 1]
BACK_RIGHT = [3, 1]
BACK = [5, 3]
BACK_LEFT = [4, 5]
LEFT = [6, 4]
FRONT_LEFT = [6, 7]

CLOCKWISE_RING = [7, 2, 0, 1, 3, 5, 4, 6]
COUNTER_CLOCKWISE_RING = [6, 4, 5, 3, 1, 0, 2, 7]

DRIVERS = {}

MAX_INTENSITY = 127
GAP_TIME = 0.08

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
    if DRIVERS.get(channel):
        DRIVERS[channel].realtime_value = intensity


def motor_off(channel):
    if DRIVERS.get(channel):
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
# HAPTIC PATTERNS
# =========================================================

def pulse_group(group, repeats=5, intensity=127, on_time=0.18, off_time=0.10):
    for _ in range(repeats):
        for m in group:
            motor_on(m, intensity)

        time.sleep(on_time)

        all_off()
        time.sleep(off_time)


def wave(group, speed=0.10, intensity=120, loops=2):
    for _ in range(loops):
        for m in group:
            all_off()
            motor_on(m, intensity)
            time.sleep(speed)
            all_off()
            time.sleep(0.04)

# =========================================================
# DEGREE LOGIC
# =========================================================

def normalize_degree(deg):
    return deg % 360


def navigate_to_degree(degree):
    degree = normalize_degree(degree)

    print(f"\n[NAVIGATION] Target Direction: {degree}°")

    if degree >= 337.5 or degree < 22.5:
        print("Direction = FRONT")
        pulse_group(FRONT, repeats=6, on_time=0.22)

    elif 22.5 <= degree < 67.5:
        print("Direction = FRONT RIGHT")
        pulse_group(FRONT_RIGHT, repeats=5, on_time=0.16)

    elif 67.5 <= degree < 112.5:
        print("Direction = RIGHT")
        pulse_group(RIGHT, repeats=6, on_time=0.18)

    elif 112.5 <= degree < 157.5:
        print("Direction = BACK RIGHT")
        pulse_group(BACK_RIGHT, repeats=5, on_time=0.16)

    elif 157.5 <= degree < 202.5:
        print("Direction = BACK")
        pulse_group(BACK, repeats=6, on_time=0.22)

    elif 202.5 <= degree < 247.5:
        print("Direction = BACK LEFT")
        pulse_group(BACK_LEFT, repeats=5, on_time=0.16)

    elif 247.5 <= degree < 292.5:
        print("Direction = LEFT")
        pulse_group(LEFT, repeats=6, on_time=0.18)

    elif 292.5 <= degree < 337.5:
        print("Direction = FRONT LEFT")
        pulse_group(FRONT_LEFT, repeats=5, on_time=0.16)

    all_off()

# =========================================================
# TESTS
# =========================================================

def test_each_motor():
    for i in range(8):
        print(f"\nTesting motor {i}")
        pulse_group([i], repeats=3, intensity=127, on_time=0.25)
        time.sleep(1)


def full_360_test():
    test_angles = [0, 45, 90, 135, 180, 225, 270, 315]

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
    print("UPDATED 360 HAPTIC NAVIGATION SYSTEM")
    print("===================================")
    print("Current physical layout:")
    print("FRONT: 6   7   2   0")
    print("BACK:  4   5   3   1")
    print("===================================")
    print("Enter degree 0-359")
    print("0 = FRONT")
    print("90 = RIGHT")
    print("180 = BACK")
    print("270 = LEFT")
    print("Commands: test, motors, q")
    print("===================================")

    while True:
        user_input = input("\nEnter Degree or Command: ").strip().lower()

        if user_input == "q":
            break

        elif user_input == "test":
            full_360_test()

        elif user_input == "motors":
            test_each_motor()

        else:
            try:
                deg = float(user_input)
                navigate_to_degree(deg)

            except ValueError:
                print("[ERROR] Invalid input")

    all_off()


if __name__ == "__main__":
    main()