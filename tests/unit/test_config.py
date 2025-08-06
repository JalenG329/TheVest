"""
Unit tests for the configuration module.
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from src.utils.config import ConfigLoader


class TestConfigLoader:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)
        
        # Create test configuration files
        base_config = {
            'LOG_LEVEL': 'INFO',
            'CAMERA': {
                'format': 'RGB888',
                'size': [640, 480]
            },
            'MODEL_PATHS': {
                'zoo_url': '/default/path'
            }
        }
        
        dev_config = {
            'LOG_LEVEL': 'DEBUG',
            'CAMERA': {
                'fps': 30
            }
        }
        
        with open(self.config_dir / 'settings.yaml', 'w') as f:
            yaml.dump(base_config, f)
        
        with open(self.config_dir / 'development.yaml', 'w') as f:
            yaml.dump(dev_config, f)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_base_config(self):
        """Test loading base configuration."""
        loader = ConfigLoader(self.config_dir)
        config = loader.load('settings')
        
        assert config['LOG_LEVEL'] == 'INFO'
        assert config['CAMERA']['format'] == 'RGB888'
        assert config['CAMERA']['size'] == [640, 480]
    
    def test_load_with_environment(self):
        """Test loading with environment-specific config."""
        loader = ConfigLoader(self.config_dir)
        config = loader.load('settings', 'development')
        
        # Should have overridden LOG_LEVEL
        assert config['LOG_LEVEL'] == 'DEBUG'
        
        # Should have merged CAMERA settings
        assert config['CAMERA']['format'] == 'RGB888'  # from base
        assert config['CAMERA']['fps'] == 30  # from dev
        assert config['CAMERA']['size'] == [640, 480]  # from base
    
    def test_get_method(self):
        """Test the get method for retrieving nested values."""
        loader = ConfigLoader(self.config_dir)
        config = loader.load('settings')
        
        assert loader.get('LOG_LEVEL') == 'INFO'
        assert loader.get('CAMERA.format') == 'RGB888'
        assert loader.get('CAMERA.size') == [640, 480]
        assert loader.get('nonexistent.key', 'default') == 'default'
    
    def test_environment_variable_override(self):
        """Test configuration override with environment variables."""
        # Set environment variable
        os.environ['HFV_LOG_LEVEL'] = 'ERROR'
        
        try:
            loader = ConfigLoader(self.config_dir)
            config = loader.load('settings')
            
            assert config['LOG_LEVEL'] == 'ERROR'
        finally:
            # Clean up
            if 'HFV_LOG_LEVEL' in os.environ:
                del os.environ['HFV_LOG_LEVEL']
