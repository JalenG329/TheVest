import numpy as np

def enhance_contrast(depth_values, enhancement_factor=2.0):
    mean_depth = np.mean(depth_values)
    enhanced = []
    for depth in depth_values:
        diff = depth - mean_depth
        enhanced_diff = diff * enhancement_factor
        enhanced_depth = mean_depth + enhanced_diff
        enhanced.append(enhanced_depth)
    return enhanced

def depth_map_to_vibrator(depth_value, min_depth=0.5, max_depth=2.5, min_v=30, max_v=127):
    depth_value = max(min_depth, min(max_depth, depth_value))
    normalized = (depth_value - min_depth) / (max_depth - min_depth)
    return int(min_v + normalized * (max_v - min_v))

# Example average depths for segments
avg_depths = [1.66, 1.73, 1.75, 1.70, 1.79, 2.08, 2.35]

print("Original depths:", avg_depths)
enhanced_depths = enhance_contrast(avg_depths, enhancement_factor=2.0)
print("Enhanced depths:", [round(d, 2) for d in enhanced_depths])

print("Method 5: Contrast-enhanced mapping")
for d in enhanced_depths:
    print(f"Depth: {d:.2f} -> Intensity: {depth_map_to_vibrator(d)}")
