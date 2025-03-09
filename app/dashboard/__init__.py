"""Dashboard module for the application."""

from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__)

# Import routes at the end to avoid circular imports
from app.dashboard import routes
