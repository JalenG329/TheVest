# IMX500 Detection Output Format

Based on the analysis of your IMX500 camera with YOLO11 model, here's what you get as detection outputs:

## Detection Output Structure

The `imx500.get_outputs(metadata)` returns a list with 4 numpy arrays:

1. **Bounding Boxes** (`network_outputs[0]`):
   - Shape: `(300, 4)`
   - Format: `[x1, y1, x2, y2]` (corner coordinates in pixels)
   - Contains up to 300 potential detection boxes

2. **Confidence Scores** (`network_outputs[1]`):
   - Shape: `(300,)`
   - Values: 0.0 to 1.0 (detection confidence)
   - Higher values indicate more confident detections

3. **Class IDs** (`network_outputs[2]`):
   - Shape: `(300,)`
   - Values: Integer class IDs (0-79 for COCO dataset)
   - Maps to class names in `coco.txt`

4. **Number of Valid Detections** (`network_outputs[3]`):
   - Shape: `(1,)`
   - Value: Number of actual detections (≤ 300)
   - Only this many detections from the arrays are valid

## Detection Dictionary Format

Each parsed detection is a dictionary with:

```python
{
    'class_name': 'person',           # Human-readable class name
    'class_id': 0,                    # COCO class ID
    'confidence': 0.85,               # Detection confidence (0-1)
    'bbox': (100, 150, 200, 300),     # Bounding box (x1, y1, x2, y2)
    'center': (150.0, 225.0),         # Center point (x, y)
    'size': (100, 150)                # Width and height
}
```

## Available Object Classes

Your model can detect 80 COCO classes including:
- person, bicycle, car, motorcycle, airplane, bus, train, truck
- bird, cat, dog, horse, sheep, cow
- bottle, chair, sofa, dining table, tv, laptop
- And many more (see `coco.txt` for full list)

## Example Usage

```python
# Get network outputs
network_outputs = imx500.get_outputs(metadata)

# Parse detections
detections = extract_detections(network_outputs, img_width, img_height, class_names, threshold=0.3)

# Use the detections
for detection in detections:
    print(f"Found {detection['class_name']} with {detection['confidence']:.2f} confidence")
    x1, y1, x2, y2 = detection['bbox']
    # Draw bounding box, trigger actions, etc.
```

## Files Created

1. **`ai_camera.py`** - Complete real-time detection with visualization
2. **`imx500_detection_proper.py`** - Optimized detection loop
3. **`detection_output_example.py`** - Single frame analysis tool

Run any of these to see live detection results!
