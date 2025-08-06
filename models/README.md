# Models Directory (`models/`)

AI model files and configurations for depth estimation and object detection in the haptic feedback vest system.

## 📁 Model Categories

### 🎯 Object Detection Models

| Model | Purpose | Size | Performance | Status |
|-------|---------|------|-------------|--------|
| **`yolo11n_silu_coco--640x640_quant_hailort_hailo8_1/`** | General object detection | Small | Fast | ✅ **Active** |
| **`starvision_yolov8m_hailo8--640x640_quant_hailort_hailo8_1/`** | Enhanced detection | Medium | Balanced | 🔄 Available |
| **`yolov8m_coco--640x640_quant_hailort_hailo8_1/`** | COCO dataset detection | Medium | Accurate | 🔄 Available |
| **`yolov8n_coco_seg--1280x1280_quant_hailort_hailo8_1/`** | Segmentation model | Large | Detailed | 🔄 Available |

### 📏 Depth Estimation Models

| Model | Purpose | Size | Accuracy | Status |
|-------|---------|------|----------|--------|
| **`fastdepth--224x224_quant_hailort_hailo8_1/`** | Real-time depth | Small | Good | ✅ **Active** |
| **`depth_anything_v2--224x224_quant_hailort_hailo8_1/`** | Advanced depth | Medium | Excellent | 🔄 Available |
| **`scdepthv3--320x256_quant_hailort_hailo8_1/`** | Scene depth | Medium | Very Good | 🔄 Available |

### 🏠 Environment-Specific Models

| Model | Purpose | Environment | Status |
|-------|---------|-------------|--------|
| **`indoor_env_best--640x640_quant_hailort_hailo8_1/`** | Indoor navigation | Indoor spaces | ✅ **Active** |
| **`indoor_env_best--640x640_quant_hailort_hailo8_2/`** | Indoor navigation v2 | Indoor spaces | 🔄 Available |
| **`indoor_env_last--640x640_quant_hailort_hailo8_1/`** | Indoor (latest) | Indoor spaces | 🔄 Available |

### 🔄 Legacy/Experimental Models

| Model | Purpose | Notes |
|-------|---------|-------|
| **`damoyolo_tinynasL35_M--640x640_quant_hailort_hailo8_1/`** | DAMO-YOLO variant | Experimental |

## 🚀 Currently Used Models

### Production Configuration (main_10.py, demo.py)

```python
# Depth estimation
depth_model = "fastdepth--224x224_quant_hailort_hailo8_1"

# Object detection (combined)
yolo_model = "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1"
indoor_model = "indoor_env_best--640x640_quant_hailort_hailo8_2"
```

### Model Combination Strategy
- **YOLO11n**: General object detection (person, chair, laptop, etc.)
- **Indoor Environment**: Specialized for doors, stairs, exits
- **FastDepth**: Real-time depth estimation for haptic feedback

## 🔧 Model Integration

### DeGiRum Loading Pattern
```python
# Standard model loading
depth_model = dg.load_model(
    "fastdepth--224x224_quant_hailort_hailo8_1", 
    "@local",
    "/home/rohan/degirum_wearable_device/models"
)

# Combined models
detection_model = CombiningCompoundModel(yolo_model, indoor_model)
```

### Model Paths
- **Primary**: `/home/rohan/degirum_wearable_device/models/`
- **Project**: `/home/rohan/haptic feedback vest final/models/`
- **Assets**: Model files also in `../assets/` directory

## 📊 Model Performance Characteristics

### Depth Models Comparison

| Model | Resolution | Speed (FPS) | Accuracy | Memory |
|-------|------------|-------------|----------|---------|
| **FastDepth** | 224x224 | 25+ | Good | Low |
| **Depth Anything V2** | 224x224 | 20+ | Excellent | Medium |
| **SCDepthV3** | 320x256 | 15+ | Very Good | Medium |

### Detection Models Comparison

| Model | Resolution | Speed (FPS) | Objects | Specialization |
|-------|------------|-------------|---------|----------------|
| **YOLO11n** | 640x640 | 20+ | 80 classes | General purpose |
| **Indoor Env** | 640x640 | 20+ | ~10 classes | Navigation-specific |
| **YOLOv8m** | 640x640 | 15+ | 80 classes | Higher accuracy |

## 🎯 Model Selection Guide

### For Real-Time Performance
```python
# Fastest combination
depth_model = "fastdepth--224x224_quant_hailort_hailo8_1"
detection_model = "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1"
```

### For Maximum Accuracy
```python
# Most accurate combination
depth_model = "depth_anything_v2--224x224_quant_hailort_hailo8_1"
detection_model = "yolov8m_coco--640x640_quant_hailort_hailo8_1"
```

### For Indoor Navigation
```python
# Optimized for indoor environments
depth_model = "fastdepth--224x224_quant_hailort_hailo8_1"
detection_model = CombiningCompoundModel(
    "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    "indoor_env_best--640x640_quant_hailort_hailo8_2"
)
```

## 🔧 Model Configuration

### File Structure
```
models/
├── model_name--resolution_quant_hailort_hailo8_1/
│   ├── model_name.hef          # Hailo model file
│   ├── model_name.json         # Configuration
│   └── model_name.json~        # Backup config
```

### Configuration Files
- **`.hef`**: Compiled Hailo model for hardware acceleration
- **`.json`**: Model metadata and configuration
- **`.json~`**: Backup configuration files

## 📈 Model Evolution

### Development Timeline
```
Initial → FastDepth + YOLO → Combined Models → Specialized Indoor
   ↓            ↓                ↓               ↓
Basic        Real-time      Multi-model    Environment-
Concept      Performance    Detection      Optimized
```

### Current Best Practice
- **Depth**: FastDepth for speed, Depth Anything V2 for accuracy
- **Detection**: YOLO11n + Indoor Environment for comprehensive coverage
- **Combination**: CombiningCompoundModel for seamless integration

## 🚀 Usage Examples

### Load Individual Models
```python
import degirum as dg

# Load depth model
depth_model = dg.load_model(
    "fastdepth--224x224_quant_hailort_hailo8_1",
    "@local",
    "/path/to/models"
)

# Load detection model
detection_model = dg.load_model(
    "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1",
    "@local", 
    "/path/to/models"
)
```

### Combined Model Setup
```python
from degirum_tools import CombiningCompoundModel

# Create combined detection model
yolo = dg.load_model("yolo11n_silu_coco--640x640_quant_hailort_hailo8_1", "@local", models_path)
indoor = dg.load_model("indoor_env_best--640x640_quant_hailort_hailo8_2", "@local", models_path)
combined_model = CombiningCompoundModel(yolo, indoor)
```

## 💡 Optimization Tips

1. **Model Selection**: Choose based on your performance vs accuracy requirements
2. **Resolution Trade-offs**: Higher resolution = better accuracy but slower processing
3. **Combined Models**: Use CombiningCompoundModel for comprehensive detection
4. **Hardware Acceleration**: All models optimized for Hailo8 acceleration
5. **Memory Management**: Consider memory usage when selecting multiple models

## 🔗 Related Assets

- **`../assets/`**: Additional model files and test data
- **`../config/`**: Model configuration files
- **`../src/`**: Model integration code examples

---

**🤖 AI-Powered Navigation**: These models enable real-time understanding of the environment for smooth haptic feedback navigation!
