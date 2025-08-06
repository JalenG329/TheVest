# Project Structure Documentation

## Overview

This document describes the reorganized structure of the Haptic Feedback Vest project, which has been transformed from a loose collection of scripts into a professional Python package.

## Directory Structure

```
haptic-feedback-vest/
├── src/                          # Main source code
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # Main application entry point
│   ├── core/                    # Core application modules
│   │   ├── __init__.py
│   │   ├── app_legacy.py        # Legacy application (was new.py)
│   │   └── tracker_app.py       # Tracker application (was new_updated_tracker.py)
│   ├── computer_vision/         # Computer vision modules
│   │   ├── __init__.py
│   │   ├── detection/           # Object detection modules
│   │   │   ├── __init__.py
│   │   │   ├── combined_detection_demo.py
│   │   │   ├── detect_image.py
│   │   │   ├── detection_fast.py
│   │   │   ├── detection_slow.py
│   │   │   ├── starvision_live_test.py
│   │   │   ├── starvision_video_test.py
│   │   │   ├── stream_api.py
│   │   │   └── tiling_detection.py
│   │   ├── depth/               # Depth estimation modules
│   │   │   ├── __init__.py
│   │   │   ├── depth_anythingv2_denoising.py
│   │   │   ├── depth_anythingv2.py
│   │   │   ├── fastdepth_denoising.py
│   │   │   ├── fastdepth.py
│   │   │   └── scdepthv3.py
│   │   ├── tracking/            # Object tracking modules
│   │   │   ├── __init__.py
│   │   │   ├── detection_to_depth_track_id_optimized.py
│   │   │   ├── detection_to_depth_track_id.py
│   │   │   └── tracker.py
│   │   └── stabilization/       # Frame stabilization modules
│   │       ├── __init__.py
│   │       ├── detection_to_simdepth_stab.py
│   │       ├── orb_stabilization_alt.py
│   │       ├── orb_stabilization.py
│   │       └── vidstab_stabilization.py
│   ├── haptic_feedback/         # Haptic feedback control
│   │   ├── __init__.py
│   │   ├── cycle_effects.py
│   │   ├── depth_sensitive_8.py
│   │   ├── depth_sensitive_actuator.py
│   │   ├── detection_depth_vibration_sim.py
│   │   ├── detection_depth_vibration.py
│   │   ├── erm_continuous_vibration.py
│   │   ├── mux.py
│   │   ├── test_erm_lrm.py
│   │   ├── test_vibrator.py
│   │   ├── vest.py
│   │   └── vibrator_threading.py
│   ├── camera/                  # Camera interface modules
│   │   ├── __init__.py
│   │   ├── ai_camera.py
│   │   ├── detection_output_example.py
│   │   ├── hailo.py
│   │   ├── imx500_debug_simple.py
│   │   ├── imx500_detection_proper.py
│   │   └── pi_camera2_implementation.py
│   └── utils/                   # Utility modules
│       ├── __init__.py
│       ├── config.py            # Configuration management
│       └── logging_config.py    # Logging setup
├── config/                      # Configuration files
│   ├── settings.yaml            # Base configuration
│   ├── development.yaml         # Development environment
│   └── production.yaml          # Production environment
├── examples/                    # Example applications
│   ├── detection_to_depth_video_test.py
│   ├── detection_to_depth.py
│   ├── detection_to_simulated_depth_simple.py
│   └── detection_to_simulated_depth.py
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests
│   │   └── test_config.py
│   └── integration/             # Integration tests
│       ├── test_system_integration.py
│       └── save_depth_values.ipynb
├── docs/                        # Documentation
│   └── DETECTION_OUTPUT_GUIDE.md
├── assets/                      # Assets and data files
│   ├── test_images/             # Test images
│   ├── coco.txt                 # COCO labels
│   ├── hailort*.log             # Hardware logs
│   ├── *.hef                    # Model files
│   └── *.rpk                    # Package files
├── models/                      # AI model directories
│   ├── damoyolo_tinynasL35_M--640x640_quant_hailort_hailo8_1/
│   ├── depth_anything_v2--224x224_quant_hailort_hailo8_1/
│   ├── fastdepth--224x224_quant_hailort_hailo8_1/
│   ├── indoor_env_best--640x640_quant_hailort_hailo8_1/
│   ├── scdepthv3--320x256_quant_hailort_hailo8_1/
│   ├── starvision_yolov8m_hailo8--640x640_quant_hailort_hailo8_1/
│   ├── yolo11n_silu_coco--640x640_quant_hailort_hailo8_1/
│   ├── yolov8m_coco--640x640_quant_hailort_hailo8_1/
│   └── yolov8n_coco_seg--1280x1280_quant_hailort_hailo8_1/
└── scripts/                     # Utility scripts
    ├── manage_models.py         # Model management
    └── setup_dev.sh             # Development setup
```

## Key Improvements

### 1. Professional Package Structure
- Proper Python package structure with `__init__.py` files
- Clear separation of concerns across modules
- Logical grouping of related functionality

### 2. Configuration Management
- YAML-based configuration files for different environments
- Environment-specific settings (development, production)
- Centralized configuration loading with environment variable support

### 3. Professional Development Tools
- `setup.py` for package installation
- `Makefile` for common development tasks
- Comprehensive `.gitignore`
- Development setup script

### 4. Testing Framework
- Separate unit and integration test directories
- Example test files for configuration and system integration
- Test data organization

### 5. Documentation
- Professional README with installation and usage instructions
- API documentation structure
- Hardware setup guides

### 6. Asset Management
- Centralized location for models, test data, and logs
- Clear separation of different asset types
- Model management scripts

## Module Descriptions

### Core Modules (`src/core/`)
- **main.py**: Primary application entry point (was main_alt.py)
- **app_legacy.py**: Legacy application logic
- **tracker_app.py**: Object tracking application

### Computer Vision (`src/computer_vision/`)
- **detection/**: Object detection using YOLO and other models
- **depth/**: Depth estimation algorithms
- **tracking/**: Object tracking across frames
- **stabilization/**: Camera shake reduction

### Haptic Feedback (`src/haptic_feedback/`)
- **vest.py**: Main vest control logic
- **vibrator_threading.py**: Threaded vibration control
- **depth_sensitive_*.py**: Depth-based feedback algorithms

### Camera (`src/camera/`)
- **ai_camera.py**: AI-enhanced camera interface
- **imx500_*.py**: Sony IMX500 camera specific code
- **pi_camera2_implementation.py**: Raspberry Pi camera interface

### Utilities (`src/utils/`)
- **config.py**: Configuration loading and management
- **logging_config.py**: Centralized logging setup

## Usage Instructions

### Installation
```bash
# Clone and setup
git clone <repository>
cd haptic-feedback-vest

# Setup development environment
./scripts/setup_dev.sh

# Or manual installation
pip install -e .
```

### Running the Application
```bash
# Development mode
make run-dev

# Production mode  
make run-prod

# Direct execution
python src/main.py --config config/production.yaml
```

### Testing
```bash
# Run all tests
make test

# Run specific test suites
make test-unit
make test-integration
```

### Model Management
```bash
# List available models
python scripts/manage_models.py list

# Validate configuration
python scripts/manage_models.py validate

# Install new model
python scripts/manage_models.py install /path/to/model
```

## Migration Notes

### File Relocations
- `main_alt.py` → `src/main.py`
- `new.py` → `src/core/app_legacy.py`
- `new_updated_tracker.py` → `src/core/tracker_app.py`
- `detection/*.py` → `src/computer_vision/detection/`
- `depth/*.py` → `src/computer_vision/depth/`
- `track_id/*.py` → `src/computer_vision/tracking/`
- `detection_to_depth_stabilization/*.py` → `src/computer_vision/stabilization/`
- `test_actuator/*.py` → `src/haptic_feedback/`
- `sony camera/*.py` → `src/camera/`
- `detection_to_depth/*.py` → `examples/`

### Configuration Changes
- Environment-specific configurations in `config/` directory
- YAML-based configuration files
- Environment variable support for overrides

### Development Workflow Changes
- Use `Makefile` for common tasks
- Professional testing framework
- Code quality tools integration
- Proper dependency management

This reorganization transforms the project from a collection of scripts into a professional, maintainable Python package suitable for production deployment and collaborative development.
