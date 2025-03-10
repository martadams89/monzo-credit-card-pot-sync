"""
WSGI entry point for the application.

This file is used by Gunicorn to run the application in production.
"""

import os
import logging
from app import create_app

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the Flask application instance
app = create_app()

if __name__ == "__main__":
    # Run the application when executed directly (not through Gunicorn)
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"Starting application on port {port}")
    app.run(host="0.0.0.0", port=port)
