# Haptic Feedback Vest for Visually Impaired Navigation

![Status](https://img.shields.io/badge/status-active-green) ![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi-red) ![Python](https://img.shields.io/badge/python-3.11-blue)

An advanced assistive wearable device that provides spatial awareness through haptic feedback for visually impaired individuals. The system uses AI-powered computer vision, depth estimation, and object detection to create smooth, intuitive vibration patterns for navigation.

## 🌟 Key Features

- **🎯 Smooth Haptic Feedback**: Advanced vibration mapping with perceptual scaling and anti-jitter technology
- **👁️ AI Object Detection**: Real-time detection of people, doors, stairs, and exits with unique vibration patterns
- **📏 Depth Sensing**: 7-segment spatial mapping providing distance information through vibration intensity
- **🔄 Object Tracking**: Persistent tracking prevents duplicate vibrations for the same objects
- **⚡ Real-time Processing**: Optimized for Raspberry Pi with hardware acceleration

## 🏗️ System Architecture

```
Camera Input → AI Models → Depth/Object Processing → Haptic Output
     ↓              ↓              ↓                    ↓
  IMX500      DeGiRum AI    Smooth Mapping      7 Vibration Motors
```

## 📁 Project Structure

- **`src/`** - Main application scripts (main_1.py through main_10.py)
- **`demo/`** - Latest demonstration script with smooth haptic feedback
- **`models/`** - AI model files for depth estimation and object detection
- **`tools/`** - Testing and analysis utilities for vibration mapping
- **`docs/`** - Technical documentation and improvement guides
- **`config/`** - Configuration files for different environments
- **`examples/`** - Example implementations and detection tutorials
- **`tests/`** - Unit and integration tests

## 🚀 Quick Start

### Hardware Requirements
- Raspberry Pi 4B+ with IMX500 camera
- 7x DRV2605 haptic motor drivers connected via TCA9548A I2C multiplexer
- Vibration motors for haptic feedback

### Software Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/aishwari/Assistive-wearable-for-VI.git
   cd "haptic feedback vest final"
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Latest Demo**
   ```bash
   python demo/demo.py  # Latest smooth haptic feedback system
   ```

## 🎮 Usage

### For Demo/Testing
```bash
# Latest smooth haptic feedback demo (recommended)
python demo/demo.py

# Production scripts (evolution of system)
python src/main_10.py  # Latest with smooth feedback + error handling
python src/main_9.py   # Previous version with exponential mapping
```

### For Development & Analysis
```bash
# Test vibration mapping improvements
python tools/test_smooth_vibration_improvements.py

# Compare different mapping strategies
python tools/mapping_comparison.py

# Monitor system performance
python tools/monitor_performance.py
```

## 🔧 Revolutionary Improvements

### Smooth Haptic Feedback System (v2.0)
- **✅ Perceptual Mapping**: Uses Stevens' power law for natural vibration perception
- **✅ Quantized Levels**: 8 distinguishable intensity levels eliminate micro-adjustments
- **✅ Hysteresis Filtering**: 0.08m threshold prevents jitter from sensor noise
- **✅ Smooth Ramping**: 40% ramp factor creates gradual intensity transitions
- **✅ Thread Safety**: Prevents race conditions in motor control

### Advanced Object Detection & Tracking
- **Multi-Model AI**: Combines YOLO11n + custom indoor environment detection
- **Persistent Tracking**: Prevents duplicate alerts using track IDs
- **Smart Cooldown**: 1-second intervals between object-specific vibrations
- **Unique Haptic Signatures**: Different patterns for person/door/stairs/exit

## 📊 Performance Metrics

| Improvement | Before | After | Gain |
|-------------|--------|-------|------|
| Micro-adjustments | 128 levels | 8 levels | **94% reduction** |
| Mid-range distinguishability | Linear mapping | Perceptual mapping | **+20 points** |
| Jitter-causing updates | Every fluctuation | 0.08m threshold | **80% reduction** |
| Processing speed | Variable | 20+ FPS | **Consistent real-time** |

## 🧪 Testing & Validation

```bash
# Comprehensive vibration system tests
python tools/test_smooth_vibration_improvements.py

# Mapping strategy comparisons
python tools/test_vibration_mapping_method2.py  # Exponential
python tools/test_vibration_mapping_method4.py  # Pattern-based
python tools/test_vibration_mapping_method5.py  # Contrast-enhanced

# Unit and integration tests
python -m pytest tests/unit/
python -m pytest tests/integration/
```

## 📖 Technical Documentation

- **[Smooth Haptic Feedback System](docs/SMOOTH_HAPTIC_FEEDBACK_SYSTEM.md)** - Complete jitter elimination guide
- **[Vibration Mapping Improvement](docs/VIBRATION_MAPPING_IMPROVEMENT.md)** - Strategy comparisons & results
- **[Test Results Analysis](docs/TEST_RESULTS_ANALYSIS.md)** - Performance validation
- **[Project Structure](docs/PROJECT_STRUCTURE.md)** - Code organization details
- **[Detection Output Guide](docs/DETECTION_OUTPUT_GUIDE.md)** - AI model configuration

## 🎯 User Experience Transformation

### Before (Jittery System)
- ❌ Constant buzzing/micro-vibrations
- ❌ Difficult to distinguish object distances
- ❌ Distracting intensity fluctuations

### After (Smooth System)
- ✅ **Smooth intensity progression** as objects approach/recede
- ✅ **8 clearly distinguishable levels** for precise distance feedback  
- ✅ **No background noise** - vibrations only when meaningful
- ✅ **Intuitive object recognition** through unique haptic signatures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is part of research into assistive technologies for visually impaired individuals.

## 🙏 Acknowledgments

- **DeGiRum** for optimized AI model integration
- **Adafruit** for comprehensive haptic feedback libraries
- **Raspberry Pi Foundation** for camera and platform support
- **Research Community** advancing assistive navigation technologies

---

**🚀 Latest Version: Smooth Haptic Feedback v2.0 - Experience the difference!**

*For detailed technical documentation and implementation guides, explore the `docs/` directory.*

## Features

- **Real-time Object Detection**: Uses YOLO models to detect various objects and obstacles
- **Depth Estimation**: Estimates distance to detected objects using multiple depth models
- **Object Tracking**: Maintains identity of objects across frames for consistent feedback
- **Frame Stabilization**: Reduces camera shake for improved tracking accuracy
- **Haptic Feedback**: Provides tactile feedback through vibration motors
- **Multi-Camera Support**: Works with PiCamera2 and Sony IMX500 cameras

## Project Structure

```
haptic-feedback-vest/
├── src/                          # Source code
│   ├── core/                     # Main application logic
│   ├── computer_vision/          # Computer vision modules
│   │   ├── detection/            # Object detection
│   │   ├── depth/                # Depth estimation
│   │   ├── tracking/             # Object tracking
│   │   └── stabilization/        # Frame stabilization
│   ├── haptic_feedback/          # Haptic feedback control
│   ├── camera/                   # Camera interfaces
│   └── utils/                    # Utility functions
├── config/                       # Configuration files
├── examples/                     # Example applications
├── tests/                        # Test suites
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
├── docs/                         # Documentation
├── assets/                       # Models and test data
├── models/                       # AI model files
└── scripts/                      # Utility scripts
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd haptic-feedback-vest
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up hardware connections (see docs/hardware_setup.md)

## Usage

### Basic Usage

Run the main application:
```bash
python src/main.py
```

### Development Mode

Run with development configuration:
```bash
python src/main.py --config config/development.yaml
```

### Production Mode

Run with production configuration:
```bash
python src/main.py --config config/production.yaml
```

## Configuration

The system uses YAML configuration files in the `config/` directory:

- `settings.yaml`: Base configuration
- `development.yaml`: Development environment settings
- `production.yaml`: Production environment settings

## Hardware Requirements

- Raspberry Pi 4 or similar
- PiCamera2 or Sony IMX500 camera
- DRV2605 haptic motor driver
- Vibration motors for haptic feedback
- I2C connection for motor control

## Models

The system supports multiple AI models:

### Detection Models
- YOLO11n (general object detection)
- Indoor environment specific models
- Custom trained models

### Depth Models
- Depth Anything V2
- FastDepth
- SCDepthV3

## Testing

Run unit tests:
```bash
python -m pytest tests/unit/
```

Run integration tests:
```bash
python -m pytest tests/integration/
```

## Examples

See the `examples/` directory for:
- Basic detection examples
- Depth estimation examples
- Combined detection and depth examples
- Camera interface examples

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

[Add your license information here]

## Authors

Haptic Feedback Vest Team

## Acknowledgments

- DeGirum for AI model integration
- OpenCV community
- Raspberry Pi Foundation
