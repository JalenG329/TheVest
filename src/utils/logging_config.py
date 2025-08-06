"""
Logging configuration for the haptic feedback vest system.
"""

import logging
import logging.config
import os
from datetime import datetime


def setup_logging(log_level="INFO", log_dir="logs"):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    
    # Create log directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"haptic_vest_{timestamp}.log")
    
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'standard'
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': log_filename,
                'formatter': 'detailed',
                'mode': 'a'
            }
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'file'],
                'level': 'DEBUG',
                'propagate': False
            }
        }
    }
    
    logging.config.dictConfig(logging_config)
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured. Log level: {log_level}")
    logger.info(f"Log file: {log_filename}")
    
    return logger


def get_logger(name):
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
