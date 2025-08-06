import time
import board
import busio
from adafruit_drv2605 import DRV2605, MODE_REALTIME, MODE_INTTRIG

from threading import Thread
i2c = busio.I2C(board.SCL, board.SDA)
drv = DRV2605(i2c)

# drv.use_LRM()

def vibrate_motor():
    drv.mode = MODE_REALTIME
    
    # Vary intensity from 30 (low) to 127 (high)
    min_intensity = 30
    max_intensity = 127
    step = 5
    delay = 0.2  # Delay between intensity changes
    
    print("Starting vibration with varying intensity...")
    
    # Gradually increase intensity from low to high
    for intensity in range(min_intensity, max_intensity + 1, step):
        drv.realtime_value = intensity
        print(f"Intensity: {intensity}")
        time.sleep(delay)
    
    # Gradually decrease intensity from high to low
    for intensity in range(max_intensity, min_intensity - 1, -step):
        drv.realtime_value = intensity
        print(f"Intensity: {intensity}")
        time.sleep(delay)
    
    # Turn off vibration
    drv.realtime_value = 0
    drv.mode = MODE_INTTRIG
    print("Vibration OFF")

vibrate_thread = Thread(target=vibrate_motor)
vibrate_thread.start()