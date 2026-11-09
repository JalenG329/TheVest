# Simple script to scan for I2C devices on each channel of the PCA9548A multiplexer.

import time
import board
import busio
import adafruit_tca9548a

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c)

print("Scanning PCA9548A channels...")

for ch in range(8):
    print(f"\nChannel {ch}:")
    try:
        addresses = mux[ch].scan()

        if addresses:
            for addr in addresses:
                print(f"  Found: 0x{addr:02X}")
        else:
            print("  No devices found")

    except Exception as e:
        print(f"  Error: {e}")

    time.sleep(0.2)