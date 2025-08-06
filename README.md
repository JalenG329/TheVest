# Haptic Feedback Vest - Navigation Assistance System

A sophisticated navigation assistance system that combines computer vision with haptic feedback to help visually impaired individuals navigate their environment safely.

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
