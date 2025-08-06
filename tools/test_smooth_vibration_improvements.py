#!/usr/bin/env python3
"""
Test script to demonstrate the smooth haptic feedback improvements in main_10.py
Shows how the new system eliminates jittery vibrations.
"""

import math
import time

# Copy of the improved functions from main_10.py
def quantize_intensity(intensity, levels=8):
    """Quantize intensity to a fixed number of distinguishable levels."""
    if intensity == 0:
        return 0
    step = 127 / (levels - 1)
    return int(round(intensity / step) * step)

def perceptual_mapping(depth_value, min_depth=0.5, max_depth=2.5):
    """Map depth using perceptual scaling (Stevens' power law)."""
    if depth_value >= max_depth:
        return 0
    if depth_value <= min_depth:
        return 127
    
    # Normalize to 0-1 range (inverted so closer = higher intensity)
    normalized = 1.0 - (depth_value - min_depth) / (max_depth - min_depth)
    
    # Stevens' power law with exponent 0.6 for vibration perception
    perceptual = math.pow(normalized, 0.6)
    
    return int(perceptual * 127)

def simulate_smooth_transition(start_depth, end_depth, steps=10):
    """Simulate smooth intensity ramping between two depths."""
    current_intensities = [0] * 7  # Simulate 7 motors
    RAMP_FACTOR = 0.4
    
    print(f"\nSimulating transition from {start_depth:.2f}m to {end_depth:.2f}m:")
    print("=" * 60)
    
    for step in range(steps):
        # Interpolate depth value
        progress = step / (steps - 1)
        current_depth = start_depth + progress * (end_depth - start_depth)
        
        # Calculate target intensity
        target_intensity = perceptual_mapping(current_depth)
        target_quantized = quantize_intensity(target_intensity)
        
        # Simulate smooth ramping for motor 0
        motor_idx = 0
        current = current_intensities[motor_idx]
        intensity_diff = target_quantized - current
        new_intensity = current + int(RAMP_FACTOR * intensity_diff)
        current_intensities[motor_idx] = new_intensity
        
        print(f"Step {step+1:2d}: Depth {current_depth:.2f}m -> Target {target_quantized:3d} -> Motor {new_intensity:3d}")
        
        # Small delay to simulate real-time processing
        time.sleep(0.1)

# Test with realistic scenarios
print("SMOOTH HAPTIC FEEDBACK IMPROVEMENTS DEMONSTRATION")
print("=" * 60)

print("\n1. QUANTIZED INTENSITY LEVELS (eliminates micro-adjustments):")
test_depths = [1.5, 1.52, 1.54, 1.56, 1.58, 1.6]
print(f"{'Depth (m)':<10} {'Raw Intensity':<12} {'Quantized':<10} {'Change'}")
print("-" * 50)

prev_quantized = None
for depth in test_depths:
    raw = perceptual_mapping(depth)
    quantized = quantize_intensity(raw)
    change = "NEW" if prev_quantized is None else f"{quantized - prev_quantized:+d}"
    print(f"{depth:<10.2f} {raw:<12d} {quantized:<10d} {change}")
    prev_quantized = quantized

print("\n2. PERCEPTUAL MAPPING vs LINEAR:")
print(f"{'Depth (m)':<10} {'Linear':<8} {'Perceptual':<12} {'Difference'}")
print("-" * 45)

for depth in [0.5, 1.0, 1.5, 2.0, 2.5]:
    # Linear mapping (old method)
    linear = int((2.5 - depth) / (2.5 - 0.5) * 127) if depth <= 2.5 else 0
    
    # Perceptual mapping (new method)
    perceptual = perceptual_mapping(depth)
    
    diff = perceptual - linear
    print(f"{depth:<10.1f} {linear:<8d} {perceptual:<12d} {diff:+d}")

print("\n3. HYSTERESIS EFFECT (prevents small fluctuations):")
HYSTERESIS_THRESHOLD = 0.08
fluctuating_depths = [1.5, 1.52, 1.48, 1.53, 1.49, 1.51, 1.6]  # Small fluctuations + real change
stable_depth = 1.5
print(f"Hysteresis threshold: {HYSTERESIS_THRESHOLD}m")
print(f"{'Input Depth':<12} {'Change':<8} {'Stable Depth':<12} {'Action'}")
print("-" * 50)

for depth in fluctuating_depths:
    change = abs(depth - stable_depth)
    if change > HYSTERESIS_THRESHOLD:
        stable_depth = depth
        action = "UPDATE"
    else:
        action = "IGNORE"
    
    print(f"{depth:<12.2f} {change:<8.3f} {stable_depth:<12.2f} {action}")

# Demonstrate smooth ramping
simulate_smooth_transition(2.0, 1.0, 8)  # Approaching object
simulate_smooth_transition(1.0, 2.0, 8)  # Moving away from object

print("\n4. KEY IMPROVEMENTS SUMMARY:")
print("✅ Quantized intensity levels (8 levels) - eliminates micro-adjustments")
print("✅ Perceptual mapping (Stevens' power law) - matches human perception") 
print("✅ Hysteresis threshold (0.08m) - prevents small fluctuation responses")
print("✅ Smooth intensity ramping (40% per update) - gradual transitions")
print("✅ Thread-safe intensity updates - prevents race conditions")
print("✅ Minimum change threshold (5 units) - reduces unnecessary updates")

print(f"\nResult: SMOOTH, non-jittery vibrations that users can clearly distinguish!")
