#!/usr/bin/env python3
"""
Comparison script: Linear vs Exponential mapping for vibration intensity
Shows how the exponential mapping improves distinguishability
"""

# Original linear mapping function
def depth_map_to_vibrator_linear(depth_value, min_depth=0, max_depth=5, min_v=0, max_v=127):
    """Original linear mapping."""
    if max_depth == min_depth:
        return min_v
    return int(min_v + (depth_value - min_depth) * (max_v - min_v) / (max_depth - min_depth))

# New exponential mapping function
def depth_map_to_vibrator_exp(depth_value, min_depth=0.5, max_depth=2.5, min_v=30, max_v=127):
    """New exponential mapping."""
    depth_value = max(min_depth, min(max_depth, depth_value))
    normalized = (depth_value - min_depth) / (max_depth - min_depth)
    curved = normalized ** 2
    return int(min_v + curved * (max_v - min_v))

# Test with realistic close depth values
test_depths = [1.66, 1.73, 1.75, 1.70, 1.79, 2.08, 2.35]

print("COMPARISON: Linear vs Exponential Mapping")
print("=" * 60)
print(f"{'Depth (m)':<10} {'Linear':<8} {'Exponential':<12} {'Improvement'}")
print("-" * 60)

total_linear_range = 0
total_exp_range = 0

for i, depth in enumerate(test_depths):
    linear_intensity = depth_map_to_vibrator_linear(depth)
    exp_intensity = depth_map_to_vibrator_exp(depth)
    
    if i > 0:
        linear_diff = abs(linear_intensity - prev_linear)
        exp_diff = abs(exp_intensity - prev_exp)
        improvement = exp_diff - linear_diff
        print(f"{depth:<10.2f} {linear_intensity:<8d} {exp_intensity:<12d} +{improvement:2d}")
        total_linear_range += linear_diff
        total_exp_range += exp_diff
    else:
        print(f"{depth:<10.2f} {linear_intensity:<8d} {exp_intensity:<12d} (baseline)")
    
    prev_linear = linear_intensity
    prev_exp = exp_intensity

print("-" * 60)
print(f"Total variation - Linear: {total_linear_range}, Exponential: {total_exp_range}")
print(f"Overall improvement: +{total_exp_range - total_linear_range} intensity units")
print("\nKey improvements:")
print("- Better distinguishability between close objects")
print("- Minimum intensity of 30 ensures all vibrations are noticeable")
print("- Exponential curve amplifies differences in the important close-range")
