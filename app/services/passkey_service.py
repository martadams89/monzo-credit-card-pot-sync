"""Service for handling passkey (WebAuthn) operations"""

import logging
import json
import base64
import secrets
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    RegistrationCredential,
    AuthenticationCredential,
)
from flask import session, current_app

log = logging.getLogger("passkey_service")

class PasskeyService:
    """Service for WebAuthn (passkey) operations"""
    
    def __init__(self, user_repository=None):
        self.user_repository = user_repository
    
    def _get_rp_id(self):
        """Get the Relying Party ID (domain name)"""
        # Use the domain without protocol and port
        host = current_app.config.get('SERVER_NAME') or 'localhost'
        if ':' in host:
            # Remove port if present
            host = host.split(':')[0]
        return host
    
    def _get_origin(self):
        """Get the origin for the application"""
        server_name = current_app.config.get('SERVER_NAME') or 'localhost:5000'
        protocol = 'https' if not server_name.startswith('localhost') else 'http'
        return f"{protocol}://{server_name}"
    
    def start_registration(self, user):
        """Start the passkey registration process for a user"""
        try:
            # Generate a random challenge for this registration
            challenge = secrets.token_bytes(32)
            
            # Convert user ID to proper format
            user_id = str(user.id).encode('utf-8')
            
            # Define registration options
            options = generate_registration_options(
                rp_id=self._get_rp_id(),
                rp_name="Monzo Credit Card Pot Sync",
                user_id=user_id,
                user_name=user.username,
                user_display_name=user.username,
                attestation="direct",
                authenticator_selection=AuthenticatorSelectionCriteria(
                    resident_key=ResidentKeyRequirement.PREFERRED,
                    user_verification=UserVerificationRequirement.PREFERRED,
                ),
            )
            
            # Store challenge in session
            session['passkey_register_challenge'] = base64.b64encode(challenge).decode('utf-8')
            
            return options_to_json(options)
            
        except Exception as e:
            log.error(f"Error starting passkey registration: {e}", exc_info=True)
            return None
    
    def complete_registration(self, user, credential_data):
        """Complete the passkey registration process"""
        try:
            # Get the stored challenge
            challenge = base64.b64decode(session.pop('passkey_register_challenge', ''))
            if not challenge:
                raise ValueError("Registration challenge not found in session")
            
            # Parse credential
            credential = RegistrationCredential.parse_raw(json.dumps(credential_data))
            
            # Verify the registration response
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self._get_rp_id(),
                expected_origin=self._get_origin(),
            )
            
            if verification.credential_id and verification.credential_public_key:
                # Store the credential information with user
                cred_id_str = base64.b64encode(verification.credential_id).decode('utf-8')
                public_key_str = base64.b64encode(verification.credential_public_key).decode('utf-8')
                
                # Add credential to user's passkeys
                if not hasattr(user, 'passkeys') or not user.passkeys:
                    user.passkeys = json.dumps([])
                
                passkeys = json.loads(user.passkeys)
                passkeys.append({
                    'id': cred_id_str,
                    'public_key': public_key_str,
                    'name': f"Passkey {len(passkeys) + 1}",
                    'created_at': str(verification.credential_device_time),
                })
                
                user.passkeys = json.dumps(passkeys)
                if self.user_repository:
                    self.user_repository.save(user)
                
                return True, "Passkey registered successfully"
            else:
                return False, "Failed to verify passkey registration"
                
        except Exception as e:
            log.error(f"Error completing passkey registration: {e}", exc_info=True)
            return False, str(e)
    
    def start_authentication(self, allow_credentials=None):
        """Start the passkey authentication process"""
        try:
            # Generate a random challenge
            challenge = secrets.token_bytes(32)
            
            # Convert allowed credentials to proper format if provided
            allowed_credentials = None
            if allow_credentials:
                allowed_credentials = [
                    {"id": base64.b64decode(cred["id"]), "type": "public-key"}
                    for cred in allow_credentials
                ]
            
            # Generate authentication options
            options = generate_authentication_options(
                rp_id=self._get_rp_id(),
                challenge=challenge,
                allow_credentials=allowed_credentials,
                user_verification=UserVerificationRequirement.PREFERRED,
            )
            
            # Store challenge in session
            session['passkey_auth_challenge'] = base64.b64encode(challenge).decode('utf-8')
            
            return options_to_json(options)
            
        except Exception as e:
            log.error(f"Error starting passkey authentication: {e}", exc_info=True)
            return None
    
    def verify_authentication(self, credential_data, user=None):
        """Verify a passkey authentication response"""
        try:
            # Get the stored challenge
            challenge = base64.b64decode(session.pop('passkey_auth_challenge', ''))
            if not challenge:
                raise ValueError("Authentication challenge not found in session")
            
            # Parse credential
            credential = AuthenticationCredential.parse_raw(json.dumps(credential_data))
            
            # Get credential_id
            credential_id = credential.id
            credential_id_bytes = base64.b64decode(credential_id)
            
            # If user is provided, verify using their public key
            if user:
                passkeys = json.loads(user.passkeys)
                matching_passkey = None
                
                for passkey in passkeys:
                    stored_id = base64.b64decode(passkey['id'])
                    if stored_id == credential_id_bytes:
                        matching_passkey = passkey
                        break
                
                if not matching_passkey:
                    return False, "No matching passkey found for this user"
                
                public_key = base64.b64decode(matching_passkey['public_key'])
                
                # Verify the authentication
                verification = verify_authentication_response(
                    credential=credential,
                    expected_challenge=challenge,
                    expected_rp_id=self._get_rp_id(),
                    expected_origin=self._get_origin(),
                    credential_public_key=public_key,
                    credential_current_sign_count=0,  # We don't track sign counts currently
                )
                
                if verification.credential_id:
                    return True, "Authentication successful"
                
            # If no user is provided, just return the credential ID for lookup
            return False, base64.b64encode(credential_id_bytes).decode('utf-8')
                
        except Exception as e:
            log.error(f"Error verifying passkey authentication: {e}", exc_info=True)
            return False, str(e)
    
    def find_user_by_credential_id(self, credential_id):
        """Find a user by credential ID"""
        if not self.user_repository:
            return None
            
        users = self.user_repository.get_all()
        for user in users:
            if not hasattr(user, 'passkeys') or not user.passkeys:
                continue
                
            passkeys = json.loads(user.passkeys)
            for passkey in passkeys:
                if passkey['id'] == credential_id:
                    return user
                    
        return None
    
    def delete_passkey(self, user, credential_id):
        """Delete a passkey for a user"""
        if not hasattr(user, 'passkeys') or not user.passkeys:
            return False, "No passkeys found for this user"
            
        passkeys = json.loads(user.passkeys)
        original_count = len(passkeys)
        
        passkeys = [pk for pk in passkeys if pk['id'] != credential_id]
        
        if len(passkeys) == original_count:
            return False, "Passkey not found"
            
        user.passkeys = json.dumps(passkeys)
        if self.user_repository:
            self.user_repository.save(user)
            
        return True, "Passkey deleted successfully"
