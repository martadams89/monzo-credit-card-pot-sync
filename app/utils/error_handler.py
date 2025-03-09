"""Central error handling utilities for consistent error handling across the application."""

import logging
from flask import flash, current_app
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    """Base exception class for service-level errors."""
    def __init__(self, message, category="error", log_level="error"):
        self.message = message
        self.category = category
        self.log_level = log_level
        super().__init__(message)

def handle_error(e, flash_message=True):
    """
    Handle errors uniformly across the application.
    
    Args:
        e: The exception to handle
        flash_message: Whether to flash a message (for web UI)
        
    Returns:
        Tuple of (success, message) for API usage
    """
    if isinstance(e, ServiceError):
        message = e.message
        category = e.category
        
        # Log based on specified level
        if e.log_level == "critical":
            logger.critical(f"Critical service error: {message}")
        elif e.log_level == "error":
            logger.error(f"Service error: {message}")
        elif e.log_level == "warning":
            logger.warning(f"Service warning: {message}")
        else:
            logger.info(f"Service info: {message}")
            
    elif isinstance(e, HTTPException):
        message = f"HTTP error {e.code}: {e.description}"
        category = "error"
        logger.error(message)
    else:
        message = str(e) or "An unexpected error occurred"
        category = "error"
        logger.exception(f"Uncaught exception: {message}")
    
    if flash_message and current_app:
        flash(message, category)
        
    return False, message
