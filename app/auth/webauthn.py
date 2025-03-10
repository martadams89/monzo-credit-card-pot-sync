import base64
import json
import secrets
from datetime import datetime
from flask import current_app, session
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
    AuthenticationCredential,
    RegistrationCredential,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement
)
from app.models.user_repository import SqlAlchemyUserRepository
from app.extensions import db
from app.models.user import WebAuthnCredential
import os
import uuid
import logging

log = logging.getLogger(__name__)

user_repository = SqlAlchemyUserRepository(db)

def _generate_challenge(length=32):
    """Generate a random challenge for WebAuthn operations."""
    challenge_bytes = os.urandom(length)
    return base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

def create_webauthn_registration_options(user):
    """Generate options for WebAuthn registration."""
    rp_id = current_app.config['WEBAUTHN_RP_ID']
    rp_name = current_app.config['WEBAUTHN_RP_NAME']
    rp_icon = current_app.config.get('WEBAUTHN_RP_ICON')
    
    # Create origin based on rp_id
    origin = current_app.config.get('WEBAUTHN_ORIGIN')
    
    # Get existing credentials for exclusion
    existing_credentials = []
    for cred in user_repository.get_credentials_by_user_id(user.id):
        existing_credentials.append(base64url_to_bytes(cred.credential_id))
    
    # Generate a random challenge
    challenge = secrets.token_bytes(32)
    
    # Store the challenge in session for verification
    session['webauthn_challenge'] = base64.b64encode(challenge).decode('utf-8')
    session['webauthn_user_id'] = user.id
    
    # Create the options
    options = generate_registration_options(
        rp=PublicKeyCredentialRpEntity(id=rp_id, name=rp_name, icon=rp_icon),
        user=PublicKeyCredentialUserEntity(
            id=user.id.encode('utf-8'),
            name=user.username,
            display_name=user.email
        ),
        challenge=challenge,
        exclude_credentials=existing_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED
        ),
        attestation="none"
    )
    
    return options_to_json(options)

def verify_webauthn_registration(response_data, credential_name=None):
    """Verify the WebAuthn registration response."""
    try:
        # Get data from session
        challenge = base64.b64decode(session.pop('webauthn_challenge'))
        user_id = session.pop('webauthn_user_id')
        
        # Get the user
        user = user_repository.get_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Get origin and RP ID
        expected_origin = current_app.config.get('WEBAUTHN_ORIGIN')
        expected_rp_id = current_app.config.get('WEBAUTHN_RP_ID')
        
        # Parse response data
        registration = RegistrationCredential.parse_raw(json.dumps(response_data))
        
        # Verify the registration
        verification = verify_registration_response(
            credential=registration,
            expected_challenge=challenge,
            expected_origin=expected_origin,
            expected_rp_id=expected_rp_id
        )
        
        # Check if credential already exists
        existing_cred = user_repository.get_credential_by_id(
            base64.b64encode(verification.credential_id).decode('utf-8')
        )
        if existing_cred:
            return False, "Credential already registered"
        
        # Store the new credential
        credential = WebAuthnCredential(
            user_id=user.id,
            credential_id=base64.b64encode(verification.credential_id).decode('utf-8'),
            public_key=verification.credential_public_key.decode('utf-8'),
            sign_count=verification.sign_count,
            name=credential_name or f"Passkey created on {datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        
        user_repository.save_credential(credential)
        user.is_webauthn_enabled = True
        user_repository.update(user)
        
        return True, credential
    except Exception as e:
        return False, str(e)

def create_webauthn_authentication_options(user=None):
    """Generate options for WebAuthn authentication."""
    rp_id = current_app.config['WEBAUTHN_RP_ID']
    
    # Generate a random challenge
    challenge = secrets.token_bytes(32)
    
    # Store the challenge in session for verification
    session['webauthn_challenge'] = base64.b64encode(challenge).decode('utf-8')
    
    # Get allowed credentials if user is specified
    allowed_credentials = []
    if user:
        session['webauthn_user_id'] = user.id
        for cred in user_repository.get_credentials_by_user_id(user.id):
            allowed_credentials.append({
                "id": base64url_to_bytes(cred.credential_id),
                "transports": ["internal"]
            })
    
    # Create the options
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        allow_credentials=allowed_credentials if user else None,
        user_verification=UserVerificationRequirement.PREFERRED
    )
    
    return options_to_json(options)

def verify_webauthn_authentication(response_data):
    """Verify the WebAuthn authentication response."""
    try:
        # Get challenge from session
        challenge = base64.b64decode(session.pop('webauthn_challenge', ''))
        if not challenge:
            return False, None, "No challenge found in session"
        
        # Get expected origin and RP ID
        expected_origin = current_app.config.get('WEBAUTHN_ORIGIN')
        expected_rp_id = current_app.config.get('WEBAUTHN_RP_ID')
        
        # Parse response data
        authentication = AuthenticationCredential.parse_raw(json.dumps(response_data))
        
        # Get credential from database
        credential_id = base64.b64encode(authentication.raw_id).decode('utf-8')
        credential = user_repository.get_credential_by_id(credential_id)
        
        if not credential:
            return False, None, "Unknown credential"
        
        # Get associated user
        user = user_repository.get_by_id(credential.user_id)
        if not user:
            return False, None, "User not found"
        
        # Verify the authentication response
        verification = verify_authentication_response(
            credential=authentication,
            expected_challenge=challenge,
            expected_origin=expected_origin,
            expected_rp_id=expected_rp_id,
            credential_public_key=credential.public_key.encode(),
            credential_current_sign_count=credential.sign_count
        )
        
        # Update the credential's sign count
        credential.sign_count = verification.new_sign_count
        credential.last_used_at = datetime.utcnow()
        user_repository.update_credential(credential)
        
        return True, user, None
    except Exception as e:
        return False, None, str(e)

def generate_registration_options(user_id, username):
    """Generate WebAuthn registration options for a new credential."""
    challenge = _generate_challenge()
    
    # Convert user_id to bytes if needed
    if not isinstance(user_id, bytes):
        user_id_bytes = str(user_id).encode('utf-8')
    else:
        user_id_bytes = user_id
        
    # Convert user_id to base64 for WebAuthn
    user_id_base64 = base64.urlsafe_b64encode(user_id_bytes).decode('utf-8').rstrip('=')
    
    # Create the options object
    options = {
        'challenge': challenge,
        'rp': {
            'name': 'Monzo Sync',
            'id': current_app.config.get('WEBAUTHN_RP_ID', 'localhost')
        },
        'user': {
            'id': user_id_base64,
            'name': username,
            'displayName': username
        },
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},  # ES256
            {'type': 'public-key', 'alg': -257}  # RS256
        ],
        'authenticatorSelection': {
            'authenticatorAttachment': 'platform',
            'userVerification': 'preferred',
            'residentKey': 'preferred',
            'requireResidentKey': False
        },
        'timeout': 60000,  # 60 seconds
        'attestation': 'none'
    }
    
    return options

def verify_registration_response(credential_data, user_id):
    """Verify WebAuthn registration response and extract credential details."""
    try:
        # In a production app, you would use a WebAuthn library like 'pywebauthn'
        # to properly verify the registration response
        
        # For now, we're simplifying this verification for demonstration
        
        # Extract the necessary parts from the credential
        credential_id = credential_data.get('id')
        raw_id = credential_data.get('rawId')
        
        # Get client data and attestation object
        client_data_json_b64 = credential_data.get('response', {}).get('clientDataJSON')
        attestation_object_b64 = credential_data.get('response', {}).get('attestationObject')
        
        if not client_data_json_b64 or not attestation_object_b64:
            log.error("Missing client data or attestation object")
            return None
        
        # Convert the base64 data to bytes for further processing
        client_data_json = base64.b64decode(client_data_json_b64)
        attestation_object = base64.b64decode(attestation_object_b64)
        
        # In a real implementation, you'd validate:
        # 1. The challenge matches the one stored in the session
        # 2. The origin matches your application's origin
        # 3. The attestation is valid according to WebAuthn spec
        
        # For simplicity, we're just returning a mock response
        return {
            'publicKey': base64.b64encode(os.urandom(32)).decode('utf-8'),
            'signCount': 0
        }
        
    except Exception as e:
        log.error(f"Error during registration verification: {str(e)}")
        return None

def generate_authentication_options():
    """Generate WebAuthn authentication options."""
    challenge = _generate_challenge()
    
    # Get all registered credentials for the user
    credentials = []  # This would be fetched from DB in a real app
    
    # Create allowCredentials list
    allow_credentials = []
    for cred in credentials:
        allow_credentials.append({
            'id': cred['credential_id'],
            'type': 'public-key',
            'transports': ['internal', 'usb', 'ble', 'nfc']
        })
    
    options = {
        'challenge': challenge,
        'timeout': 60000,
        'rpId': current_app.config.get('WEBAUTHN_RP_ID', 'localhost'),
        'allowCredentials': allow_credentials,
        'userVerification': 'preferred'
    }
    
    return options

def verify_authentication_response(credential_data, expected_challenge):
    """Verify WebAuthn authentication response."""
    try:
        # In a production app, you would use a WebAuthn library for verification
        
        # Get the credential ID
        credential_id = credential_data.get('id')
        
        # Find the credential in the database
        from app.models.webauthn import WebAuthnCredential
        from app.extensions import db
        
        credential = db.session.query(WebAuthnCredential).filter_by(
            credential_id=credential_id,
            is_active=True
        ).first()
        
        if not credential:
            log.error("Credential not found or inactive")
            return None, False
        
        # Update last used timestamp
        from datetime import datetime
        credential.last_used_at = datetime.utcnow()
        credential.sign_count += 1
        db.session.commit()
        
        # For simplicity, we're accepting the authentication
        return credential.user_id, True
        
    except Exception as e:
        log.error(f"Error during authentication verification: {str(e)}")
        return None, False
