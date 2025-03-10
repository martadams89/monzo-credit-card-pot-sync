import pyotp
import qrcode
import io
import base64
import secrets
from flask import current_app
from datetime import datetime, timedelta

def generate_totp_secret():
    """Generate a random TOTP secret."""
    # Create a random 20-byte (160-bit) secret
    random_bytes = secrets.token_bytes(20)
    # Encode it in Base32 as required by TOTP
    return base64.b32encode(random_bytes).decode('utf-8')

def generate_totp_uri(secret, email, issuer='Monzo Sync'):
    """Generate a TOTP URI for QR code generation."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)

def verify_totp(secret, code):
    """Verify a TOTP code against a secret."""
    # Create a TOTP instance with the secret
    totp = pyotp.TOTP(secret)
    
    # Verify the code (with a 30-second grace period in both directions)
    return totp.verify(code, valid_window=1)

def generate_qr_code_data_uri(uri):
    """Generate a data URI for the QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def generate_backup_codes(count=8, length=6):
    """Generate backup codes for 2FA recovery."""
    codes = []
    for _ in range(count):
        # Generate a random code with the specified length
        code = secrets.token_hex(length // 2).upper()
        codes.append(code)
    return codes

def hash_backup_code(code):
    """Hash a backup code for secure storage."""
    from werkzeug.security import generate_password_hash
    return generate_password_hash(code)

def verify_backup_code(hashed_code, provided_code):
    """Verify a backup code against its hash."""
    from werkzeug.security import check_password_hash
    return check_password_hash(hashed_code, provided_code)
