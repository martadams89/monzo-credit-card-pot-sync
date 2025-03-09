"""Repository for user database operations."""

import logging
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User
from app.extensions import db

log = logging.getLogger("user_repository")

class SqlAlchemyUserRepository:
    """SQL Alchemy implementation of user repository."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def save(self, user):
        """Save a user."""
        try:
            if not user.id:
                self.db.session.add(user)
            self.db.session.commit()
            return True
        except SQLAlchemyError as e:
            log.error(f"Error saving user: {e}")
            self.db.session.rollback()
            return False
    
    def get_by_id(self, user_id):
        """Get a user by ID."""
        return User.query.get(user_id)
    
    def get_by_username(self, username):
        """Get a user by username."""
        return User.query.filter_by(username=username).first()
    
    def get_by_email(self, email):
        """Get a user by email."""
        return User.query.filter_by(email=email).first()
    
    def find_by_email_token(self, token):
        """Find a user by email verification token.
        
        Args:
            token: Email verification token
            
        Returns:
            User: User object or None if not found
        """
        return User.query.filter_by(email_verification_token=token).first()
    
    def count(self):
        """Count all users"""
        return User.query.count()
    
    def get_all(self):
        """Get all users"""
        return User.query.all()
