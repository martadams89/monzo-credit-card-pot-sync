"""
WSGI entry point for the application.

This module serves as the entry point for WSGI servers like Gunicorn to run the
Flask application. It sets up necessary environment and creates the application instance.
"""

import os
import sys
import logging

# Filter CBOR2 deprecation warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning, 
                       message=r"The cbor\.(decoder|types|encoder) module has been deprecated.*")

# Add the project root directory to Python path for proper imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the Flask application factory
from app import create_app

# Create the application instance
application = create_app()

# Configure root logger if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Run the application in debug mode when executed directly
    # Use environment variable for configuration, defaulting to false
    application.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
