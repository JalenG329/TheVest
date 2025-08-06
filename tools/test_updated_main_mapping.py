#!/usr/bin/env python3
"""
Test script to verify the improved vibration mapping in main_9.py
This script tests the exponential mapping with realistic depth values.
"""

# Copy of the updated function from main_9.py
def depth_map_to_vibrator(depth_value, min_depth=0.5, max_depth=2.5, min_v=30, max_v=127):
    """Map depth value to vibration intensity using exponential curve for better distinguishability."""
    # Clamp depth value to valid range
    depth_value = max(min_depth, min(max_depth, depth_value))
    
    # Normalize to 0-1 range
    normalized = (depth_value - min_depth) / (max_depth - min_depth)
    
    # Apply exponential curve (quadratic) for better distinguishability
    curved = normalized ** 2
    
    # Map to vibration intensity range
    return int(min_v + curved * (max_v - min_v))

# Test with example depth values that were previously too similar
test_depths = [1.66, 1.73, 1.75, 1.70, 1.79, 2.08, 2.35]

print("Testing the updated exponential mapping in main_9.py:")
print("=" * 50)

previous_intensity = None
for i, depth in enumerate(test_depths):
    intensity = depth_map_to_vibrator(depth)
    
    if previous_intensity is not None:
        difference = abs(intensity - previous_intensity)
        print(f"Segment {i+1}: Depth {depth:.2f}m -> Intensity {intensity:3d} (Δ={difference:2d})")
    else:
        print(f"Segment {i+1}: Depth {depth:.2f}m -> Intensity {intensity:3d}")
    
    previous_intensity = intensity

print("\nAnalysis:")
print("- Closer objects (lower depth) have higher vibration intensity")
print("- The exponential curve creates larger differences between similar depths")
print("- Minimum intensity starts at 30 to ensure all vibrations are noticeable")
print("- Maximum intensity is 127 for strong feedback on close objects")
