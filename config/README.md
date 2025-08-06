# Configuration Directory (`config/`)

Configuration files for different environments and system settings in the haptic feedback vest system.

## 📁 Configuration Files

| File | Purpose | Environment | Usage |
|------|---------|-------------|-------|
| **`settings.yaml`** | Base configuration | All | Core system settings |
| **`development.yaml`** | Development settings | Development | Testing & debugging |
| **`production.yaml`** | Production settings | Production | Live deployment |

## 🔧 Configuration Categories

### 📊 **`settings.yaml` - Base Configuration**
**Purpose**: Core system settings used across all environments

**Key Sections**:
```yaml
# Camera Configuration
camera:
  width: 1280
  height: 720
  format: "RGB888"

# Model Configuration  
models:
  depth_model: "fastdepth--224x224_quant_hailort_hailo8_1"
  detection_model: "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1"
  indoor_model: "indoor_env_best--640x640_quant_hailort_hailo8_2"

# Haptic Feedback
haptic:
  intensity_levels: 8
  ramp_factor: 0.4
  hysteresis_threshold: 0.08
  min_intensity_change: 5

# Processing Parameters
processing:
  temporal_smoothing_alpha: 0.3
  gaussian_kernel_size: 5
  gaussian_sigma: 1.5
```

### 🛠️ **`development.yaml` - Development Settings**
**Purpose**: Enhanced logging and debugging for development

**Key Features**:
```yaml
# Debugging
debug:
  verbose_logging: true
  show_depth_display: true
  print_motor_changes: true
  save_test_frames: true

# Performance Monitoring
monitoring:
  track_fps: true
  memory_profiling: true
  latency_analysis: true

# Testing
testing:
  use_test_data: false
  simulation_mode: false
  mock_hardware: false
```

### 🚀 **`production.yaml` - Production Settings**
**Purpose**: Optimized settings for live deployment

**Key Features**:
```yaml
# Performance Optimization
performance:
  minimize_logging: true
  disable_display: true
  optimize_memory: true

# Reliability
reliability:
  error_recovery: true
  automatic_restart: true
  hardware_monitoring: true

# User Experience
ux:
  smooth_feedback: true
  reduced_latency: true
  battery_optimization: true
```

## 🎯 Configuration Usage

### Environment-Specific Loading
```python
import yaml

# Load base configuration
with open('config/settings.yaml', 'r') as f:
    base_config = yaml.safe_load(f)

# Load environment-specific overrides
with open('config/development.yaml', 'r') as f:
    dev_config = yaml.safe_load(f)

# Merge configurations
config = {**base_config, **dev_config}
```

### Direct Configuration Access
```python
# Access camera settings
camera_width = config['camera']['width']
camera_height = config['camera']['height']

# Access haptic parameters
ramp_factor = config['haptic']['ramp_factor']
intensity_levels = config['haptic']['intensity_levels']

# Access model paths
depth_model = config['models']['depth_model']
```

## 🔧 Key Configuration Parameters

### 📹 Camera Settings
```yaml
camera:
  width: 1280              # Camera resolution width
  height: 720              # Camera resolution height  
  format: "RGB888"         # Color format
  framerate: 30            # Target FPS
```

### 🎮 Haptic Feedback Parameters
```yaml
haptic:
  intensity_levels: 8          # Quantized vibration levels
  ramp_factor: 0.4            # Smooth transition speed (0.1-0.9)
  hysteresis_threshold: 0.08   # Anti-jitter threshold (meters)
  min_intensity_change: 5      # Minimum change to update motor
  cooldown_time: 1.0          # Object detection cooldown (seconds)
```

### 🤖 AI Model Configuration
```yaml
models:
  depth_model: "fastdepth--224x224_quant_hailort_hailo8_1"
  detection_model: "yolo11n_silu_coco--640x640_quant_hailort_hailo8_1"
  indoor_model: "indoor_env_best--640x640_quant_hailort_hailo8_2"
  model_path: "/home/rohan/degirum_wearable_device/models"
```

### ⚙️ Processing Parameters
```yaml
processing:
  temporal_smoothing_alpha: 0.3    # Temporal smoothing factor
  gaussian_kernel_size: 5          # Depth denoising kernel
  gaussian_sigma: 1.5              # Gaussian blur sigma
  depth_model_size: 224            # Depth model input size
```

## 🚀 Environment-Specific Features

### 🛠️ Development Environment
- **Verbose Logging**: Detailed console output for debugging
- **Visual Display**: Shows depth maps and detection overlays
- **Performance Monitoring**: FPS, memory, and latency tracking
- **Test Mode**: Option to use recorded test data

### 🚀 Production Environment
- **Optimized Performance**: Minimal logging, maximum speed
- **Reliability Features**: Error recovery and automatic restart
- **Battery Optimization**: Reduced computational overhead
- **User-Focused**: Smooth haptic feedback prioritized

## 📊 Configuration Hierarchy

```
settings.yaml (Base)
    ↓
development.yaml (Development Overrides)
    ↓
production.yaml (Production Overrides)
```

### Override Priority
1. **Command Line Arguments** (highest priority)
2. **Environment-Specific Config** (development.yaml/production.yaml)
3. **Base Configuration** (settings.yaml)
4. **Default Values** (lowest priority)

## 🔧 Customization Guide

### Adding New Parameters
```yaml
# In settings.yaml
new_feature:
  parameter1: value1
  parameter2: value2
```

### Environment Overrides
```yaml
# In development.yaml
new_feature:
  parameter1: debug_value1  # Override for development

# In production.yaml  
new_feature:
  parameter1: prod_value1   # Override for production
```

### Code Integration
```python
# Access new parameters
feature_param = config['new_feature']['parameter1']
```

## 📈 Performance Tuning

### For Speed (Real-time Priority)
```yaml
haptic:
  ramp_factor: 0.6          # Faster transitions
  intensity_levels: 6       # Fewer levels for speed

processing:
  temporal_smoothing_alpha: 0.5  # Less smoothing
```

### For Smoothness (Quality Priority)
```yaml
haptic:
  ramp_factor: 0.3          # Smoother transitions
  intensity_levels: 10      # More levels for precision

processing:
  temporal_smoothing_alpha: 0.2  # More smoothing
```

### For Battery Life
```yaml
camera:
  framerate: 20             # Reduced FPS

processing:
  optimize_memory: true     # Memory optimization
  reduce_computations: true # Computational efficiency
```

## 💡 Best Practices

1. **Version Control**: Keep all three config files in git
2. **Environment Variables**: Use for sensitive/system-specific values
3. **Validation**: Validate config on startup
4. **Documentation**: Comment complex parameters
5. **Testing**: Test with different configurations

## 🔗 Integration Points

### Main Scripts
```python
# In main_10.py, demo.py
config = load_configuration(environment='production')
RAMP_FACTOR = config['haptic']['ramp_factor']
INTENSITY_LEVELS = config['haptic']['intensity_levels']
```

### Tool Integration
```python
# In tools/monitor_performance.py
monitoring_config = config['monitoring']
if monitoring_config['track_fps']:
    start_fps_monitoring()
```

---

**⚙️ System Configuration**: These files enable flexible, environment-aware configuration for optimal haptic feedback performance across development and production scenarios!
