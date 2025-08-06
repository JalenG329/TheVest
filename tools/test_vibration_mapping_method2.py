import numpy as np

# Example average depths for segments
avg_depths = [1.66, 1.73, 1.75, 1.70, 1.79, 2.08, 2.35]

# Method 2: Non-linear (exponential) mapping

def depth_map_to_vibrator_exp(depth_value, min_depth=0.5, max_depth=2.5, min_v=30, max_v=127):
    depth_value = max(min_depth, min(max_depth, depth_value))
    normalized = (depth_value - min_depth) / (max_depth - min_depth)
    curved = normalized ** 2  # Exponential curve
    return int(min_v + curved * (max_v - min_v))

print("Method 2: Exponential mapping")
for d in avg_depths:
    print(f"Depth: {d:.2f} -> Intensity: {depth_map_to_vibrator_exp(d)}")
