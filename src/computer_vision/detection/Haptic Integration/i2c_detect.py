import board
import busio
import adafruit_tca9548a
i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)
for i in range(8):
    print(f"Scanning channel {i}...")
    if mux[i].try_lock():
        print(mux[i].scan())
        mux[i].unlock()
