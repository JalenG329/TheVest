import numpy as np
import time

def vibrate_motor_pattern(intensity, delay=0.1):
    # Simulate vibration pattern (print instead of real hardware)
    if intensity > 100:
        for _ in range(2):
            print(f"Pulse: {intensity}")
            time.sleep(delay/3)
            print("Pulse: 0")
            time.sleep(delay/3)
    else:
        print(f"Steady: {intensity}")
        time.sleep(delay)
        print("Steady: 0")

# Example intensities for segments
intensities = [42, 43, 44, 43, 45, 52, 59, 110, 127]

print("Method 4: Pattern-based feedback simulation")
for i, intensity in enumerate(intensities):
    print(f"Segment {i+1}:")
    vibrate_motor_pattern(intensity)
