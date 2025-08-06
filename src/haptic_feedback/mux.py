import adafruit_tca9548a
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG

import board
import busio

import time
from threading import Thread

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

# Select channel 3 (index 3)
# drv1 = DRV2605(mux[3])
drv2 = DRV2605(mux[1]) 

def vibrate_motor():
    # drv1.mode = MODE_REALTIME
    # drv1.realtime_value = 30  # Set to a lower intensity for testing
    drv2.mode = MODE_REALTIME
    drv2.realtime_value = 100  # Set to a lower intensity for testing
    print("Vibration ON (via mux channel 1)")
    time.sleep(5)
    # drv1.realtime_value = 0
    # drv1.mode = MODE_INTTRIG
    drv2.realtime_value = 0
    drv2.mode = MODE_INTTRIG
    print("Vibration OFF")

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