import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG

import board
import busio

import time
from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

# rotate through each chaneel in this order 
# Assign the mux channels to variables for clarity, mapping to drv1 through drv8
drv1 = DRV2605(mux[1])  # Channel 1
drv2 = DRV2605(mux[3])  # Channel 3
drv3 = DRV2605(mux[6])  # Channel 6
drv4 = DRV2605(mux[5])  # Channel 5
drv5 = DRV2605(mux[4])  # Channel 4
drv6 = DRV2605(mux[7])  # Channel 7
drv7 = DRV2605(mux[2])  # Channel 2
drv8 = DRV2605(mux[0])  # Channel 0
 
def vibrate_motor():
    drvs = [drv1, drv2, drv3, drv4, drv5, drv6, drv7, drv8]
    for idx, drv in enumerate(drvs, start=1):
        drv.mode = MODE_REALTIME
        drv.realtime_value = 127  # Set to desired intensity
        print(f"Vibration ON (drv{idx})")
        time.sleep(1)  # Vibrate each motor for 1 second
        drv.realtime_value = 0
        drv.mode = MODE_INTTRIG
        print(f"Vibration OFF (drv{idx})")

vibrate_thread = Thread(target=vibrate_motor)
vibrate_thread.start()

# mux[0] #8
# mux[1] #1
# mux[2] #7
# mux[3] #2
# mux[4] #5
# mux[5] #4
# mux[6] #3
# mux[7] #6