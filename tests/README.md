# Tests Directory (`tests/`)

Comprehensive testing suite for the haptic feedback vest system ensuring reliability and performance.

## 📁 Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
├── integration/             # Integration tests for system components
├── test_degirum_tracking.py # DeGiRum tracking system tests  
└── test_track_id.py        # Track ID functionality tests
```

## 🧪 Test Categories

### 🔬 **Unit Tests** (`unit/`)
**Purpose**: Test individual functions and components in isolation

**Test Areas**:
- **Haptic Feedback Functions**: Vibration mapping, intensity calculation
- **Depth Processing**: Depth map conversion, segment analysis
- **Object Detection**: Detection parsing, track ID generation
- **Utility Functions**: Helper functions and data processing

**Example Tests**:
```python
def test_depth_map_to_vibrator():
    """Test depth to vibration intensity mapping"""
    assert depth_map_to_vibrator(1.0) == 106  # Close object
    assert depth_map_to_vibrator(2.5) == 0    # Far object
    
def test_quantize_intensity():
    """Test intensity quantization"""
    assert quantize_intensity(65) == 72       # Quantized level
    assert quantize_intensity(0) == 0         # Zero handling
```

### 🔗 **Integration Tests** (`integration/`)
**Purpose**: Test component interactions and system workflows

**Test Scenarios**:
- **Camera to Haptic Pipeline**: End-to-end processing
- **Model Integration**: AI model loading and inference
- **Hardware Interface**: I2C communication and motor control
- **Error Handling**: System resilience and recovery

**Example Tests**:
```python
def test_full_processing_pipeline():
    """Test complete frame processing workflow"""
    frame = capture_test_frame()
    depth_result = depth_model.predict(frame)
    detection_result = detection_model.predict(frame)
    haptic_output = process_results(depth_result, detection_result)
    assert haptic_output is not None
```

## 🎯 Current Test Files

### **`test_degirum_tracking.py`**
**Purpose**: Validates DeGiRum object tracking functionality

**Test Coverage**:
- ✅ Track ID generation and persistence
- ✅ Object association across frames
- ✅ Tracking accuracy and performance
- ✅ Error handling in tracking pipeline

**Key Tests**:
```python
def test_track_id_persistence():
    """Verify track IDs persist across frames"""
    
def test_object_association():
    """Test object matching between frames"""
    
def test_tracking_performance():
    """Measure tracking accuracy and speed"""
```

### **`test_track_id.py`**
**Purpose**: Specific testing of track ID functionality

**Test Coverage**:
- ✅ Track ID uniqueness
- ✅ ID generation algorithms
- ✅ Collision detection and resolution
- ✅ Track ID cleanup and memory management

**Key Tests**:
```python
def test_track_id_uniqueness():
    """Ensure generated track IDs are unique"""
    
def test_id_collision_handling():
    """Test behavior when ID collisions occur"""
    
def test_track_cleanup():
    """Verify old tracks are properly cleaned up"""
```

## 🚀 Running Tests

### All Tests
```bash
# Run complete test suite
python -m pytest tests/

# With verbose output
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=src/
```

### Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/

# Integration tests only  
python -m pytest tests/integration/

# Specific test file
python -m pytest tests/test_track_id.py
```

### Individual Tests
```bash
# Specific test function
python -m pytest tests/test_track_id.py::test_track_id_uniqueness

# With detailed output
python -m pytest tests/test_track_id.py::test_track_id_uniqueness -s
```

## 📊 Test Coverage Areas

### ✅ **Haptic Feedback System**
```python
# Smooth vibration functionality
test_perceptual_mapping()          # Stevens' power law implementation
test_intensity_quantization()      # 8-level quantization
test_smooth_ramping()              # Gradual intensity changes
test_hysteresis_filtering()        # Anti-jitter functionality
test_thread_safety()              # Motor control locks
```

### ✅ **Computer Vision Pipeline**
```python
# AI model integration
test_depth_model_loading()         # Model initialization
test_detection_model_inference()   # Object detection
test_depth_processing()            # Depth map conversion
test_7_segment_analysis()          # Spatial segmentation
```

### ✅ **Object Tracking**
```python
# Tracking functionality
test_track_id_generation()         # ID creation
test_object_persistence()          # Cross-frame tracking
test_cooldown_system()             # Duplicate prevention
test_tracking_accuracy()           # Performance metrics
```

### ✅ **System Integration**
```python
# End-to-end workflows
test_camera_to_haptic_pipeline()   # Complete processing
test_error_recovery()              # Resilience testing
test_performance_benchmarks()      # Speed and memory
test_hardware_interface()          # I2C and motor control
```

## 🧪 Test Data and Fixtures

### Test Data Sources
- **Recorded Video**: Real camera footage for testing
- **Synthetic Scenes**: Generated test scenarios
- **Edge Cases**: Challenging detection scenarios
- **Performance Data**: Benchmarking datasets

### Common Fixtures
```python
@pytest.fixture
def sample_depth_map():
    """Provides standardized depth map for testing"""
    
@pytest.fixture  
def mock_detection_result():
    """Provides mock AI detection results"""
    
@pytest.fixture
def haptic_system():
    """Initializes haptic feedback system for testing"""
```

## 📈 Performance Testing

### Benchmarking Tests
```python
def test_processing_speed():
    """Measure frame processing rate"""
    
def test_memory_usage():
    """Monitor memory consumption"""
    
def test_latency_analysis():
    """Measure end-to-end latency"""
    
def test_haptic_response_time():
    """Measure vibration response timing"""
```

### Load Testing
```python
def test_sustained_operation():
    """Test system under continuous load"""
    
def test_multiple_objects():
    """Test with many simultaneous detections"""
    
def test_rapid_movements():
    """Test with fast camera movements"""
```

## 🔧 Test Configuration

### Test Settings
```python
# In conftest.py
TEST_CONFIG = {
    'use_mock_hardware': True,      # Safe testing without hardware
    'test_data_path': 'test_data/', # Test video and images
    'benchmark_iterations': 100,    # Performance test iterations
    'timeout_seconds': 30,          # Test timeout limit
}
```

### Hardware Mocking
```python
@pytest.fixture
def mock_motors():
    """Mock haptic motors for testing without hardware"""
    
@pytest.fixture
def mock_camera():
    """Mock camera for testing without hardware"""
```

## ✅ Test Quality Metrics

### Coverage Goals
- **Unit Tests**: >90% code coverage
- **Integration Tests**: All major workflows
- **Performance Tests**: Key metrics benchmarked
- **Error Handling**: All exception paths tested

### Test Quality Indicators
```bash
# Coverage report
python -m pytest --cov=src/ --cov-report=html

# Performance benchmarks
python -m pytest tests/performance/ --benchmark-only

# Test timing
python -m pytest --durations=10
```

## 💡 Testing Best Practices

### Writing New Tests
1. **Clear naming**: Test names describe what's being tested
2. **Isolated tests**: Each test is independent
3. **Mock external dependencies**: Use fixtures for hardware
4. **Assert specific values**: Check exact expected outcomes
5. **Test edge cases**: Include boundary conditions

### Maintaining Tests
1. **Update with code changes**: Keep tests current
2. **Regular execution**: Run tests frequently
3. **Performance monitoring**: Track test execution time
4. **Coverage analysis**: Identify untested code paths

## 🔗 Integration with Development

### Pre-commit Testing
```bash
# Run quick tests before committing
python -m pytest tests/unit/ --maxfail=1
```

### Continuous Integration
```bash
# Full test suite for CI/CD
python -m pytest tests/ --cov=src/ --cov-fail-under=85
```

### Development Workflow
```bash
# Test-driven development
python -m pytest tests/test_new_feature.py --watch
```

---

**🧪 Quality Assurance**: Comprehensive testing ensures the haptic feedback vest system delivers reliable, smooth navigation assistance for visually impaired users!
