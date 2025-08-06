import time
import board
import busio
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG

from threading import Thread
i2c = busio.I2C(board.SCL, board.SDA)
drv = DRV2605(i2c)

def vibrate_motor():
    drv.mode = MODE_REALTIME

    drv.realtime_value = 127
    print("Vibration ON")
    time.sleep(5)

    drv.realtime_value = 0
    drv.mode = MODE_INTTRIG
    print("Vibration OFF")

vibrate_thread = Thread(target=vibrate_motor)
vibrate_thread.start()