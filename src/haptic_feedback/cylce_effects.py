import time
import board
import busio
import adafruit_drv2605

# Initialize I2C bus using board's SCL and SDA pins
i2c = busio.I2C(board.SCL, board.SDA)

# Create DRV2605 haptic driver object
drv = adafruit_drv2605.DRV2605(i2c)

# Start cycling through all haptic effects
effect_id = 1
while True:
    # Set the current effect in the sequence
    drv.sequence[0] = adafruit_drv2605.Effect(effect_id)
    # Play the selected effect
    print(f"Playing effect {effect_id}")
    # Play the effect
    drv.play()
    # Wait for 1 second
    time.sleep(1)
    # Stop the effect
    drv.stop()
    # Move to the next effect
    effect_id += 1
    # Loop back to the first effect after the last one
    if effect_id > 47:
        effect_id = 1
