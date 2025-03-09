"""Enhanced logging configuration."""

import os
import json
import logging
import logging.config
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
            
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ('args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
                          'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
                          'msecs', 'message', 'msg', 'name', 'pathname', 'process',
                          'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName'):
                log_data[key] = value
            
        return json.dumps(log_data)

def setup_logging(app):
    """Setup logging for the application."""
    log_level = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_format = app.config.get('LOG_FORMAT', 'json')
    
    # Ensure logs directory exists
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'standard' if log_format != 'json' else 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'standard' if log_format != 'json' else 'json',
            'filename': os.path.join(log_dir, 'app.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'standard' if log_format != 'json' else 'json',
            'filename': os.path.join(log_dir, 'error.log'),
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
        }
    }
    
    formatters = {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json': {
            '()': JSONFormatter
        }
    }
    
    logging.config.dictConfig({
        'version': 1,
        'formatters': formatters,
        'handlers': handlers,
        'loggers': {
            '': {  # Root logger
                'handlers': ['console', 'file', 'error_file'],
                'level': log_level,
            },
            'app': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            'werkzeug': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False
            }
        }
    })
    
    app.logger.info(f"Logging set up with level {log_level}")
