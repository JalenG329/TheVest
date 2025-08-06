# Examples Directory (`examples/`)

Educational examples and tutorials demonstrating various aspects of the haptic feedback vest system.

## 📁 Contents Overview

| Script | Purpose | Complexity | Focus Area |
|--------|---------|------------|------------|
| **`detection_to_depth_video_test.py`** | Video-based depth detection testing | 🟢 Beginner | Integration |
| **`detection_to_depth.py`** | Basic detection + depth combination | 🟡 Intermediate | Core Concepts |
| **`detection_to_simulated_depth_simple.py`** | Simple simulated depth demo | 🟢 Beginner | Learning |
| **`detection_to_simulated_depth.py`** | Advanced simulated depth system | 🟡 Intermediate | Development |

## 🎓 Learning Path

### 🟢 **Beginner Level**

#### 1. `detection_to_simulated_depth_simple.py`
**Purpose**: Introduction to depth simulation and object detection

**What you'll learn**:
- Basic object detection workflow
- Simple depth simulation techniques
- Console output interpretation
- Foundation concepts

```bash
python examples/detection_to_simulated_depth_simple.py
```

**Expected Output**:
```
Object detected: person at simulated depth 1.5m
Vibration intensity: 72
```

#### 2. `detection_to_depth_video_test.py`
**Purpose**: Video-based testing without hardware requirements

**What you'll learn**:
- Video processing pipeline
- Detection-to-depth workflow
- Performance analysis
- Testing methodologies

```bash
python examples/detection_to_depth_video_test.py
```

### 🟡 **Intermediate Level**

#### 3. `detection_to_depth.py`
**Purpose**: Real-world detection and depth estimation

**What you'll learn**:
- AI model integration
- Camera interface usage
- Real-time processing
- Error handling

```bash
python examples/detection_to_depth.py
```

**Requirements**: Camera hardware (IMX500 or PiCamera2)

#### 4. `detection_to_simulated_depth.py`
**Purpose**: Advanced simulation with realistic scenarios

**What you'll learn**:
- Complex scene simulation
- Multi-object depth estimation
- Performance optimization
- Advanced algorithms

```bash
python examples/detection_to_simulated_depth.py
```

## 🔧 Technical Concepts Demonstrated

### Object Detection Integration
```python
# Common pattern across examples
detection_result = detection_model.predict(frame)
for detection in detection_result._inference_results:
    label = detection['label']
    bbox = detection['bbox']
    # Process detection...
```

### Depth Estimation
```python
# Real depth (detection_to_depth.py)
depth_result = depth_model.predict(frame)
depth_map = process_depth_result(depth_result)

# Simulated depth (simulated examples)
simulated_depth = calculate_depth_from_bbox(bbox, assumptions)
```

### Vibration Mapping
```python
# Convert depth to haptic feedback
intensity = depth_map_to_vibrator(depth_value)
vibrate_motor(intensity, motor_driver)
```

## 🎯 Use Cases by Example

### For Learning (`detection_to_simulated_depth_simple.py`)
- **New developers** understanding the system
- **Students** learning computer vision concepts
- **Researchers** exploring haptic feedback basics

### For Testing (`detection_to_depth_video_test.py`)
- **Quality assurance** testing
- **Performance benchmarking**
- **Algorithm validation** without hardware

### For Development (`detection_to_depth.py`)
- **Real-world testing** with actual hardware
- **Integration debugging**
- **Performance optimization**

### For Research (`detection_to_simulated_depth.py`)
- **Algorithm development**
- **Scenario testing**
- **Academic research** and publications

## 🚀 Quick Start Guide

### 1. Start Simple
```bash
# Begin with the simplest example
python examples/detection_to_simulated_depth_simple.py
```

### 2. Progress Gradually
```bash
# Move to video testing
python examples/detection_to_depth_video_test.py
```

### 3. Real Hardware
```bash
# Try with actual camera (if available)
python examples/detection_to_depth.py
```

### 4. Advanced Concepts
```bash
# Explore advanced simulation
python examples/detection_to_simulated_depth.py
```

## 📚 Educational Value

### Computer Vision Concepts
- **Object Detection**: YOLO model usage and output interpretation
- **Depth Estimation**: Various depth calculation methods
- **Image Processing**: Frame handling and conversion

### Haptic Feedback Principles
- **Spatial Mapping**: Converting 2D/3D space to tactile feedback
- **Intensity Mapping**: Distance-to-vibration conversion
- **User Experience**: Intuitive feedback design

### System Integration
- **Real-time Processing**: Camera to haptic pipeline
- **Error Handling**: Robust system design
- **Performance**: Optimization techniques

## 🔧 Hardware Requirements

| Example | Camera Required | Haptic Hardware | Notes |
|---------|----------------|-----------------|--------|
| `detection_to_simulated_depth_simple.py` | ❌ No | ❌ No | Pure simulation |
| `detection_to_depth_video_test.py` | ❌ No | ❌ No | Video file input |
| `detection_to_depth.py` | ✅ Yes | ⚠️ Optional | Real camera needed |
| `detection_to_simulated_depth.py` | ❌ No | ❌ No | Advanced simulation |

## 📊 Performance Expectations

### Simple Examples (Simulated)
- **Processing Speed**: Very fast (no AI inference)
- **Resource Usage**: Minimal
- **Learning Value**: High for concepts

### Hardware Examples (Real)
- **Processing Speed**: 15-25 FPS on Raspberry Pi
- **Resource Usage**: Moderate (AI models)
- **Learning Value**: High for integration

## 🎓 Educational Progression

```
Simple Simulation → Video Testing → Real Hardware → Advanced Research
       ↓                ↓               ↓              ↓
   Understand        Test Ideas     Real World    Push Boundaries
   Concepts         & Algorithms    Integration    & Innovation
```

## 💡 Tips for Learners

1. **Start Simple**: Begin with simulated examples to understand concepts
2. **Read Console Output**: Examples provide detailed logging for learning
3. **Modify Parameters**: Experiment with detection thresholds and depth ranges
4. **Compare Approaches**: Run multiple examples to see different techniques
5. **Progress Gradually**: Move from simulation to real hardware step by step

## 🔗 Related Resources

- **Main Scripts**: See `../src/` for production implementations
- **Tools**: See `../tools/` for testing and analysis utilities
- **Documentation**: See `../docs/` for detailed technical guides

---

**📖 Learning Goal**: These examples provide a structured path from basic concepts to advanced haptic feedback system implementation!
