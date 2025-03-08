"""Service for handling user authentication"""

import logging
import secrets
import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta
import uuid

log = logging.getLogger("auth_service")

class AuthService:
    """Service for user authentication including 2FA"""
    
    def __init__(self, user_repository, email_service=None):
        self.user_repository = user_repository
        self.email_service = email_service
        self.verification_codes = {}  # In-memory storage for verification codes
        
    def generate_email_verification_token(self, user):
        """Generate a unique token for email verification"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(days=1)
        
        # Store the token in the user's record
        user.email_verification_token = token
        user.email_verification_expiry = expiry
        self.user_repository.save(user)
        
        return token
        
    def verify_email(self, token):
        """Verify a user's email address using a token"""
        user = self.user_repository.find_by_email_token(token)
        
        if not user:
            return False, "Invalid verification token"
            
        if user.email_verification_expiry < datetime.now():
            return False, "Verification token has expired"
            
        # Mark email as verified
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expiry = None
        self.user_repository.save(user)
        
        return True, "Email verified successfully"
        
    def generate_totp_secret(self, user):
        """Generate a new TOTP secret for a user"""
        # Generate a secret key
        secret = pyotp.random_base32()
        
        # Save to user record
        user.totp_secret = secret
        user.totp_enabled = False  # Not enabled until verified
        self.user_repository.save(user)
        
        return secret
        
    def get_totp_qr_code(self, user, app_name="Monzo Pot Sync"):
        """Generate a QR code for TOTP setup"""
        if not user.totp_secret:
            self.generate_totp_secret(user)
            
        # Create a TOTP provisioning URI
        totp = pyotp.TOTP(user.totp_secret)
        uri = totp.provisioning_uri(user.email, issuer_name=app_name)
        
        # Generate QR code
        img = qrcode.make(uri)
        buffer = io.BytesIO()
        img.save(buffer)
        
        # Convert to base64 for embedding in HTML
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return qr_base64
        
    def verify_totp(self, user, code):
        """Verify a TOTP code"""
        if not user.totp_secret:
            return False
            
        totp = pyotp.TOTP(user.totp_secret)
        return totp.verify(code)
        
    def enable_totp(self, user, code):
        """Enable TOTP for a user after verification"""
        if self.verify_totp(user, code):
            user.totp_enabled = True
            self.user_repository.save(user)
            return True
        return False
        
    def disable_totp(self, user, password):
        """Disable TOTP for a user"""
        if user.check_password(password):
            user.totp_enabled = False
            self.user_repository.save(user)
            return True
        return False
        
    def generate_email_code(self, user):
        """Generate a short verification code and send via email"""
        # Generate a 6-digit code
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        expiry = datetime.now() + timedelta(minutes=15)
        
        # Store the code with expiry
        self.verification_codes[user.id] = {
            'code': code,
            'expiry': expiry
        }
        
        # Send the code via email if email service is available
        if self.email_service:
            self.email_service.send_two_factor_code(user, code)
            
        return code
        
    def verify_email_code(self, user_id, code):
        """Verify an email verification code"""
        if user_id not in self.verification_codes:
            return False
            
        stored = self.verification_codes[user_id]
        if stored['expiry'] < datetime.now():
            # Clean up expired code
            del self.verification_codes[user_id]
            return False
            
        if stored['code'] == code:
            # Clean up used code
            del self.verification_codes[user_id]
            return True
            
        return False
