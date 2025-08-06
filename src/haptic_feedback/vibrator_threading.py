import time
import board
import busio
import adafruit_drv2605

from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
drv = adafruit_drv2605.DRV2605(i2c)

stop_vibration = False

def vibrate_motor():
    """
    Continuously activates the vibration motor in a loop until the 'stop_vibration' flag is set.

    Within each iteration, the function:
    - Sets the vibration effect to effect number 47 using the DRV2605 driver.
    - Starts the vibration motor.
    - Waits for 0.1 seconds to maintain the vibration.
    - Stops the vibration motor.

    Assumes the existence of global variables and objects:
    - 'stop_vibration': a boolean flag to control the loop.
    - 'drv': an instance of the DRV2605 driver.
    - 'adafruit_drv2605': the module providing the Effect class.
    - 'time': the time module for sleep functionality.
    """
    while not stop_vibration:
        drv.sequence[0] = adafruit_drv2605.Effect(47)
        drv.play()
        time.sleep(.1)  # Vibrate for 0.1 seconds
        drv.stop()

def count():
    """
    Counts from 1 to 10, printing each number at one-second intervals.

    This function iterates ten times, pausing for one second between each iteration,
    and prints the current count (starting from 1) to the standard output.
    """
    for i in range (10): time.sleep(1); print(f"{i+1}")


vibrate_thread = Thread(target=vibrate_motor)

vibrate_thread.start()
count()
stop_vibration = True
vibrate_thread.join()
