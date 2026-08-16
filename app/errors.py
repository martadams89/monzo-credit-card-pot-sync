from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class AuthException(Exception):
    """Custom exception for authentication errors."""


class PotNotFoundError(Exception):
    """Raised when a pot cannot be located on any Monzo account."""


class PotTransferError(Exception):
    """Raised when a deposit to or withdrawal from a pot fails."""
