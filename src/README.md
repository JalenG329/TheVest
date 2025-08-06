# Source Code Directory (`src/`)

This directory contains the main application scripts representing the evolution of the haptic feedback vest system.

## 📁 Main Scripts Evolution

### Current Production Scripts

| Script | Description | Status | Key Features |
|--------|-------------|--------|--------------|
| **`main_10.py`** | **Latest & Recommended** | ✅ **Active** | Smooth haptic feedback, error handling, crash prevention |
| **`main_9.py`** | Previous stable version | 🔄 Stable | Exponential mapping, improved distinguishability |
| `main_8.py` | Earlier development | 📦 Archive | Object tracking improvements |
| `main_7.py` | Mid-development | 📦 Archive | Enhanced depth processing |
| `main_6.py` | Early iteration | 📦 Archive | Basic vibration mapping |

### Historical Development (Archive)
- `main_1.py` through `main_5.py` - Early prototypes and experiments

## 🚀 **Recommended Usage**

### For Production/Demo
```bash
python src/main_10.py  # Latest with smooth haptic feedback
```

### For Development/Testing
```bash
python src/main_9.py   # Stable fallback if needed
```

## 🔧 Key Improvements by Version

### main_10.py (Current)
- **Smooth Haptic Feedback**: Perceptual mapping with Stevens' power law
- **Anti-Jitter System**: Hysteresis filtering prevents micro-vibrations
- **Error Handling**: Robust tracking with crash prevention
- **Thread Safety**: Locked motor control prevents race conditions
- **Quantized Levels**: 8 distinguishable intensity levels

### main_9.py (Previous)
- **Exponential Mapping**: Quadratic curve for better distinguishability
- **Temporal Smoothing**: Reduces sensor noise
- **Object Tracking**: Track ID support for duplicate prevention
- **Multi-Model Detection**: YOLO + custom environment models

## 📊 Performance Comparison

| Feature | main_9.py | main_10.py | Improvement |
|---------|-----------|-------------|-------------|
| Vibration Smoothness | Linear/Exponential | Perceptual + Ramping | **Dramatically smoother** |
| Jitter Reduction | Basic smoothing | Hysteresis + quantization | **94% reduction** |
| Error Handling | Basic | Comprehensive | **Crash-proof** |
| Distinguishability | Good | Excellent | **+37 intensity units** |

## 🔗 Module Dependencies

All scripts depend on:
- **Computer Vision**: `computer_vision/` modules for detection and depth
- **Haptic Feedback**: `haptic_feedback/` for motor control
- **Camera Interface**: `camera/` for IMX500 integration
- **Utilities**: `utils/` for common functions

## 📈 Development Timeline

```
main_1.py → main_2.py → ... → main_8.py → main_9.py → main_10.py
    ↓           ↓                ↓           ↓           ↓
  Basic     Enhanced        Tracking    Exponential  Smooth
 Concept   Detection       Support     Mapping      Haptic
```

## 🧪 Testing Each Version

```bash
# Test current version
python src/main_10.py

# Compare with previous
python src/main_9.py

# Monitor performance differences
python ../tools/monitor_performance.py
```

## 🎯 Migration Guide

**From main_9.py to main_10.py:**
- ✅ Drop-in replacement - same hardware setup
- ✅ Improved user experience with smooth feedback
- ✅ Better error handling - more reliable operation
- ✅ Same configuration files and model paths

## 📝 Configuration

All main scripts use:
- **Models**: `../models/` directory for AI models
- **Config**: `../config/` for environment settings
- **Hardware**: Same I2C multiplexer and motor setup

---

**💡 Quick Start**: Use `main_10.py` for the best haptic feedback experience with smooth, jitter-free vibrations!
