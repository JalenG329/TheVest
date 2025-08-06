#!/usr/bin/env python3
"""
Model management script for the haptic feedback vest system.
"""

import argparse
import os
import shutil
from pathlib import Path
import yaml


def list_models(models_dir):
    """List all available models."""
    models_path = Path(models_dir)
    if not models_path.exists():
        print(f"Models directory not found: {models_dir}")
        return
    
    print("Available models:")
    for model_dir in models_path.iterdir():
        if model_dir.is_dir():
            print(f"  - {model_dir.name}")


def validate_models(config_file, models_dir):
    """Validate that all models in config exist."""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    models_path = Path(models_dir)
    missing_models = []
    
    # Check detection models
    for model_name in config.get('MODEL_PATHS', {}).get('detection_models', []):
        model_path = models_path / model_name
        if not model_path.exists():
            missing_models.append(model_name)
    
    # Check depth models
    for model_name in config.get('MODEL_PATHS', {}).get('depth_models', []):
        model_path = models_path / model_name
        if not model_path.exists():
            missing_models.append(model_name)
    
    if missing_models:
        print("Missing models:")
        for model in missing_models:
            print(f"  - {model}")
        return False
    else:
        print("All models found!")
        return True


def install_model(model_path, models_dir):
    """Install a model to the models directory."""
    source_path = Path(model_path)
    target_path = Path(models_dir) / source_path.name
    
    if not source_path.exists():
        print(f"Source model not found: {model_path}")
        return False
    
    try:
        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            shutil.copy2(source_path, target_path)
        print(f"Model installed: {source_path.name}")
        return True
    except Exception as e:
        print(f"Error installing model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Model management for haptic feedback vest')
    parser.add_argument('--models-dir', default='models', help='Models directory path')
    parser.add_argument('--config', default='config/settings.yaml', help='Configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List available models')
    
    # Validate command
    subparsers.add_parser('validate', help='Validate models exist')
    
    # Install command
    install_parser = subparsers.add_parser('install', help='Install a model')
    install_parser.add_argument('model_path', help='Path to model to install')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_models(args.models_dir)
    elif args.command == 'validate':
        validate_models(args.config, args.models_dir)
    elif args.command == 'install':
        install_model(args.model_path, args.models_dir)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
