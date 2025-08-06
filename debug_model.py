#!/usr/bin/env python3
"""
Debug script to test model loading and inspect model properties
"""
import degirum as dg
import json

def debug_model():
    print("=== MODEL DEBUG INFORMATION ===")
    
    # Load the model
    try:
        model = dg.load_model(
            model_name="indoor_env_last--640x640_quant_hailort_hailo8_1",
            inference_host_address="@local",
            zoo_url="/home/rohan/degirum_wearable_device/models"
        )
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        return
    
    # Print model attributes
    print(f"\nModel type: {type(model)}")
    print(f"Model attributes: {[attr for attr in dir(model) if not attr.startswith('_')]}")
    
    # Check if model has class names/labels
    if hasattr(model, 'class_names'):
        print(f"\nClass names: {model.class_names}")
    if hasattr(model, 'labels'):
        print(f"Labels: {model.labels}")
    if hasattr(model, 'categories'):
        print(f"Categories: {model.categories}")
    
    # Check model input/output shape
    if hasattr(model, 'input_shape'):
        print(f"Input shape: {model.input_shape}")
    if hasattr(model, 'output_shape'):
        print(f"Output shape: {model.output_shape}")
    
    # Check model configuration
    if hasattr(model, 'model_info'):
        print(f"Model info: {model.model_info}")
    
    # Try to get more detailed info
    try:
        # Some models store info in different attributes
        for attr in ['_model_info', 'model_parameters', 'config']:
            if hasattr(model, attr):
                attr_value = getattr(model, attr)
                print(f"{attr}: {attr_value}")
    except Exception as e:
        print(f"Error accessing model details: {e}")

if __name__ == "__main__":
    debug_model()
