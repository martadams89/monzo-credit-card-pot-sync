"""Settings management for the application."""

from flask import Blueprint

settings_bp = Blueprint('settings', __name__)

from app.settings import routes
