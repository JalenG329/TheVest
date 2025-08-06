"""
Configuration loader for the haptic feedback vest system.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Configuration loader that supports environment-specific configs."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._config = {}
    
    def load(self, config_name: str = "settings", environment: str = None) -> Dict[str, Any]:
        """
        Load configuration from YAML files.
        
        Args:
            config_name: Base configuration file name (without .yaml)
            environment: Environment-specific config (development, production, etc.)
        
        Returns:
            Merged configuration dictionary
        """
        
        # Load base configuration
        base_config_path = self.config_dir / f"{config_name}.yaml"
        if base_config_path.exists():
            with open(base_config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
        
        # Load environment-specific configuration if specified
        if environment:
            env_config_path = self.config_dir / f"{environment}.yaml"
            if env_config_path.exists():
                with open(env_config_path, 'r') as f:
                    env_config = yaml.safe_load(f) or {}
                
                # Merge configurations (environment overrides base)
                self._config = self._merge_configs(self._config, env_config)
        
        # Override with environment variables
        self._override_with_env_vars()
        
        return self._config
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two configuration dictionaries.
        
        Args:
            base: Base configuration
            override: Override configuration
        
        Returns:
            Merged configuration
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _override_with_env_vars(self):
        """Override configuration with environment variables."""
        
        # Define environment variable mappings
        env_mappings = {
            'HFV_LOG_LEVEL': ['LOG_LEVEL'],
            'HFV_DEBUG': ['DEBUG'],
            'HFV_MODEL_ZOO': ['MODEL_PATHS', 'zoo_url'],
            'HFV_CAMERA_FORMAT': ['CAMERA', 'format'],
            'HFV_CAMERA_WIDTH': ['CAMERA', 'size', 0],
            'HFV_CAMERA_HEIGHT': ['CAMERA', 'size', 1],
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(self._config, config_path, env_value)
    
    def _set_nested_value(self, config: Dict[str, Any], path: list, value: str):
        """Set a nested value in the configuration dictionary."""
        current = config
        
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert value types
        final_key = path[-1]
        if isinstance(value, str):
            if value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif '.' in value and value.replace('.', '').isdigit():
                value = float(value)
        
        current[final_key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        keys = key.split('.')
        current = self._config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except KeyError:
            return default


# Global configuration instance
config = ConfigLoader()
