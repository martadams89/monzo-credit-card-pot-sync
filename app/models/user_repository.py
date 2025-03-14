import logging
from typing import List, Optional, Tuple, Any
from datetime import datetime, timedelta
import secrets
import uuid
import json
from sqlalchemy import desc, or_, and_, asc, func
from flask import request, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.user import User, Role
from app.models.audit import AuditLog, UserSession
from app.models.api_key import ApiKey  # Fixed import
from app.models.webauthn import WebAuthnCredential

log = logging.getLogger(__name__)

class SqlAlchemyUserRepository:
    """Repository for User model database operations."""
    
    def __init__(self, db) -> None:
        self._session = db.session

    # User CRUD operations
    def get_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        return self._session.query(User).filter_by(id=user_id).one_or_none()
    
    def get_by_username(self, username: str) -> User:
        """Get user by username."""
        return self._session.query(User).filter_by(username=username).one_or_none()
        
    def get_by_email(self, email: str) -> User:
        """Get user by email."""
        return self._session.query(User).filter_by(email=email).one_or_none()
    
    def get_by_verification_token(self, token: str) -> User:
        """Get user by email verification token."""
        return self._session.query(User).filter_by(email_verification_token=token).one_or_none()
        
    def get_by_reset_token(self, token: str) -> User:
        """Get user by password reset token."""
        return self._session.query(User).filter_by(password_reset_token=token).one_or_none()
    
    def save(self, user: User) -> User:
        """Save or update a user."""
        try:
            self._session.add(user)
            self._session.commit()
            return user
        except Exception as e:
            self._session.rollback()
            log.error(f"Error saving user: {str(e)}")
            raise
    
    # Alias for consistency
    create = save
    update = save
            
    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        try:
            user = self.get_by_id(user_id)
            if user:
                self._session.delete(user)
                self._session.commit()
                return True
            return False
        except Exception as e:
            self._session.rollback()
            log.error(f"Error deleting user: {str(e)}")
            raise
    
    # User querying methods
    def get_all(self) -> list[User]:
        """Get all users."""
        return self._session.query(User).all()
        
    def get_admins(self) -> list[User]:
        """Get all admin users."""
        return self._session.query(User).filter_by(role=Role.ADMIN.value).all()
            
    # Enhanced user search and filtering methods
    def search_users(self, search_term="", sort_by="username", order="asc", page=1, per_page=10, is_active=None):
        """Search and filter users with pagination."""
        query = self._session.query(User)
        
        # Apply search filter if provided
        if search_term:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%")
                )
            )
        
        # Filter by active status if specified
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
            
        # Apply sorting
        if order.lower() == "desc":
            query = query.order_by(desc(getattr(User, sort_by)))
        else:
            query = query.order_by(asc(getattr(User, sort_by)))
            
        # Apply pagination
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page).all()
        
    def count_users(self, search_term="", is_active=None):
        """Count total users matching the criteria."""
        query = self._session.query(func.count(User.id))
        
        # Apply search filter if provided
        if search_term:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%")
                )
            )
        
        # Filter by active status if specified
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
            
        return query.scalar()
    
    # Analytics methods
    def count_users_with_2fa(self):
        """Count users with 2FA enabled."""
        return self._session.query(func.count(User.id)).filter(User.is_totp_enabled == True).scalar()
        
    def count_users_with_webauthn(self):
        """Count users with WebAuthn enabled."""
        return self._session.query(func.count(User.id)).filter(User.is_webauthn_enabled == True).scalar()
        
    def count_recent_registrations(self, days=7):
        """Count users registered in the last X days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self._session.query(func.count(User.id)).filter(User.created_at >= cutoff_date).scalar()
        
    def count_recent_logins(self, days=1):
        """Count users who logged in during the last X days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self._session.query(func.count(User.id)).filter(User.last_login_at >= cutoff_date).scalar()
        
    def count_failed_login_attempts(self, days=1):
        """Count failed login attempts in the last X days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self._session.query(func.sum(User.login_attempts)).filter(
            and_(
                User.login_attempts > 0,
                User.updated_at >= cutoff_date
            )
        ).scalar() or 0
        
    def count_locked_accounts(self):
        """Count currently locked accounts."""
        current_time = datetime.utcnow()
        return self._session.query(func.count(User.id)).filter(
            and_(
                User.locked_until.isnot(None),
                User.locked_until > current_time
            )
        ).scalar()
        
    # WebAuthn credential methods
    def save_credential(self, credential: WebAuthnCredential) -> WebAuthnCredential:
        """Save a WebAuthn credential."""
        self._session.add(credential)
        self._session.commit()
        return credential
    
    def get_credential_by_id(self, credential_id: str) -> WebAuthnCredential:
        """Get credential by ID."""
        return self._session.query(WebAuthnCredential).filter_by(credential_id=credential_id).one_or_none()
        
    def get_credentials_by_user_id(self, user_id: str) -> list[WebAuthnCredential]:
        """Get all credentials for a user."""
        return self._session.query(WebAuthnCredential).filter_by(user_id=user_id).all()
        
    def update_credential(self, credential: WebAuthnCredential) -> WebAuthnCredential:
        """Update a WebAuthn credential."""
        self._session.add(credential)
        self._session.commit()
        return credential
        
    def delete_credential(self, credential: WebAuthnCredential) -> None:
        """Delete a WebAuthn credential."""
        self._session.delete(credential)
        self._session.commit()
        
    # Audit log methods
    def add_audit_log(self, user_id=None, target_user_id=None, action=None, 
                     details=None, ip_address=None, user_agent=None) -> AuditLog:
        """Add an audit log entry."""
        if ip_address is None and request:
            ip_address = request.remote_addr
            
        if user_agent is None and request:
            user_agent = request.user_agent.string if request.user_agent else None
            
        audit_log = AuditLog(
            user_id=user_id,
            target_user_id=target_user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._session.add(audit_log)
        self._session.commit()
        return audit_log
        
    # Alias for consistency
    log_audit = add_audit_log
        
    def get_audit_logs(self, user_id=None, action=None, start_date=None, end_date=None, page=1, per_page=50):
        """Get audit logs with filtering and pagination."""
        query = self._session.query(AuditLog)
        
        # Apply filters if provided
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
            
        if action:
            query = query.filter(AuditLog.action == action)
            
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
            
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
            
        # Sort by creation date (newest first)
        query = query.order_by(desc(AuditLog.created_at))
        
        # Apply pagination
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page).all()
        
    def count_audit_logs(self, user_id=None, action=None, start_date=None, end_date=None):
        """Count total audit logs matching the criteria."""
        query = self._session.query(func.count(AuditLog.id))
        
        # Apply filters if provided
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
            
        if action:
            query = query.filter(AuditLog.action == action)
            
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
            
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
            
        return query.scalar()
        
    def get_audit_logs_for_user(self, user_id, subject_only=False, limit=None, page=1, per_page=20):
        """Get audit logs for a specific user (as subject or target)."""
        if subject_only:
            query = self._session.query(AuditLog).filter(AuditLog.user_id == user_id)
        else:
            query = self._session.query(AuditLog).filter(
                or_(
                    AuditLog.user_id == user_id,
                    AuditLog.target_user_id == user_id
                )
            )
            
        # Sort by creation date (newest first)
        query = query.order_by(desc(AuditLog.created_at))
        
        if limit:
            return query.limit(limit).all()
        else:
            # Apply pagination
            offset = (page - 1) * per_page
            return query.offset(offset).limit(per_page).all()
            
    def count_audit_logs_for_user(self, user_id, subject_only=False):
        """Count total audit logs for a user."""
        if subject_only:
            query = self._session.query(func.count(AuditLog.id)).filter(AuditLog.user_id == user_id)
        else:
            query = self._session.query(func.count(AuditLog.id)).filter(
                or_(
                    AuditLog.user_id == user_id,
                    AuditLog.target_user_id == user_id
                )
            )
        return query.scalar()
        
    def get_distinct_audit_actions(self):
        """Get a list of distinct audit action types."""
        return [r[0] for r in self._session.query(AuditLog.action).distinct().all()]
        
    # Session management methods
    def record_session(self, user_id, session_id, ip_address=None, user_agent=None):
        """Record a new user session."""
        if ip_address is None and request:
            ip_address = request.remote_addr
            
        if user_agent is None and request:
            user_agent = request.user_agent.string if request.user_agent else None
            
        # Determine device info from user agent
        device_info = "Unknown device"
        if user_agent:
            # Very simple device detection
            lower_ua = user_agent.lower()
            if "mobile" in lower_ua or "android" in lower_ua or "iphone" in lower_ua or "ipad" in lower_ua:
                device_info = "Mobile device"
            elif "tablet" in lower_ua:
                device_info = "Tablet"
            elif "windows" in lower_ua or "macintosh" in lower_ua or "linux" in lower_ua:
                device_info = "Desktop"
                
        # Set expiry based on app configuration
        expires_at = datetime.utcnow() + timedelta(
            seconds=current_app.config.get("PERMANENT_SESSION_LIFETIME", 86400)
        )
        
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            expires_at=expires_at
        )
        
        self._session.add(session)
        self._session.commit()
        return session
    
    # Alias for consistency
    record_login = record_session
        
    def get_session_by_id(self, session_id):
        """Get a session by its ID."""
        return self._session.query(UserSession).filter_by(id=session_id).one_or_none()
        
    def get_active_sessions(self, user_id):
        """Get all active sessions for a user."""
        current_time = datetime.utcnow()
        return self._session.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                or_(
                    UserSession.expires_at.is_(None),
                    UserSession.expires_at > current_time
                )
            )
        ).order_by(desc(UserSession.last_activity_at)).all()
        
    def get_login_history(self, user_id, limit=5):
        """Get recent login history for a user."""
        return self._session.query(UserSession).filter_by(user_id=user_id).order_by(
            desc(UserSession.created_at)
        ).limit(limit).all()
        
    def revoke_session(self, session_id):
        """Revoke a specific session."""
        session = self._session.query(UserSession).filter_by(id=session_id).one_or_none()
        if session:
            session.is_active = False
            self._session.commit()
        return session
        
    def revoke_all_sessions_except_current(self, user_id, current_session_id):
        """Revoke all sessions for a user except the current one."""
        sessions = self._session.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.session_id != current_session_id
            )
        ).all()
        
        for session in sessions:
            session.is_active = False
            
        self._session.commit()
        return len(sessions)
        
    def update_session_activity(self, session_id):
        """Update the last activity timestamp for a session."""
        session = self._session.query(UserSession).filter_by(session_id=session_id).one_or_none()
        if session:
            session.last_activity_at = datetime.utcnow()
            self._session.commit()
        return session
        
    # API key management methods
    def create_api_key(self, user_id, name, expires_in_days=None):
        """Create a new API key for a user."""
        # Generate a secure random key
        key_value = secrets.token_urlsafe(32)
        
        # Hash the key for storage
        key_hash = generate_password_hash(key_value)
        
        # Set expiry date if specified
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
        # Create and save the API key
        api_key = ApiKey(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            expires_at=expires_at
        )
        
        self._session.add(api_key)
        self._session.commit()
        
        # Return both the model and the raw key (which won't be retrievable later)
        return api_key, key_value
        
    def get_api_keys(self, user_id):
        """Get all API keys for a user."""
        return self._session.query(ApiKey).filter_by(user_id=user_id).order_by(desc(ApiKey.created_at)).all()
        
    def get_api_key_by_id(self, key_id):
        """Get an API key by its ID."""
        return self._session.query(ApiKey).filter_by(id=key_id).one_or_none()
        
    def verify_api_key(self, key_value):
        """Verify an API key and return the associated user if valid."""
        # Find all active API keys
        active_keys = self._session.query(ApiKey).filter(
            and_(
                ApiKey.is_active == True,
                or_(
                    ApiKey.expires_at.is_(None),
                    ApiKey.expires_at > datetime.utcnow()
                )
            )
        ).all()
        
        # Check each key
        for api_key in active_keys:
            if check_password_hash(api_key.key_hash, key_value):
                # Update last used timestamp
                api_key.last_used_at = datetime.utcnow()
                self._session.commit()
                
                # Get and return the associated user
                user = self._session.query(User).filter_by(id=api_key.user_id).one_or_none()
                return user, api_key
                
        return None, None
        
    def revoke_api_key(self, key_id):
        """Revoke an API key."""
        api_key = self._session.query(ApiKey).filter_by(id=key_id).one_or_none()
        if api_key:
            api_key.is_active = False
            self._session.commit()
        return api_key