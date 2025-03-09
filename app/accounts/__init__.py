"""Account management module."""

from flask import Blueprint

accounts_bp = Blueprint('accounts', __name__)

# Import routes at the end to avoid circular imports
from app.accounts import routes
