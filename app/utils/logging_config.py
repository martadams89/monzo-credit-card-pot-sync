import logging
import json
import os
from logging.config import dictConfig

class CustomJSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing by log systems."""
    
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def configure_logging(app):
    """Configure structured logging for the application."""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    dictConfig({
        'version': 1,
        'formatters': {
            'json': {
                '()': CustomJSONFormatter
            },
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default' if app.debug else 'json',
                'level': log_level
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': os.path.join(app.config.get('LOG_DIR', 'logs'), 'app.log'),
                'maxBytes': 10485760,  # 10 MB
                'backupCount': 10,
                'level': log_level
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console', 'file']
        }
    })
