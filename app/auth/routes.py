"""Authentication routes"""

from flask import render_template, redirect, url_for, flash, request, current_app, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models.user import User
from app.auth.forms import LoginForm, RegistrationForm, TwoFactorSetupForm, TwoFactorVerifyForm, ChangePasswordForm
from app.extensions import db
from app.services.auth_service import AuthService
from app.services.passkey_service import PasskeyService
from app.services.container import container
import os
import json
from datetime import datetime

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        return redirect(next_page)
        
    return render_template('auth/login.html', form=form, title='Sign In')

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration - only available on first run or in dev mode"""
    # Only allow registration if:
    # 1. No users exist (first setup)
    # 2. We're in development mode
    user_count = User.query.count()
    is_dev_mode = os.environ.get('FLASK_ENV') == 'development'
    
    if user_count > 0 and not is_dev_mode:
        flash('Registration is disabled.', 'error')
        return redirect(url_for('auth.login'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        # First user is always admin
        is_admin = user_count == 0
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=is_admin
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form, title='Register')

@auth_bp.route('/two-factor/setup', methods=['GET', 'POST'])
@login_required
def two_factor_setup():
    """Setup two-factor authentication"""
    auth_service = AuthService(user_repository=None)  # We'll use current_user directly
    
    form = TwoFactorSetupForm()
    
    # Generate QR code for TOTP setup
    qr_code = auth_service.get_totp_qr_code(current_user)
    secret = current_user.totp_secret
    
    if form.validate_on_submit():
        if auth_service.enable_totp(current_user, form.verification_code.data):
            flash('Two-factor authentication has been enabled successfully.', 'success')
            return redirect(url_for('auth.security_settings'))
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    return render_template('auth/two_factor_setup.html', 
                          form=form, 
                          qr_code=qr_code, 
                          secret=secret)

@auth_bp.route('/two-factor/disable', methods=['POST'])
@login_required
def disable_two_factor():
    """Disable two-factor authentication"""
    auth_service = AuthService(user_repository=None)
    
    password = request.form.get('password')
    
    if auth_service.disable_totp(current_user, password):
        flash('Two-factor authentication has been disabled.', 'success')
    else:
        flash('Incorrect password. Two-factor authentication remains enabled.', 'error')
    
    return redirect(url_for('auth.security_settings'))

@auth_bp.route('/two-factor/verify', methods=['GET', 'POST'])
def two_factor_verify():
    """Verify two-factor authentication during login"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    form = TwoFactorVerifyForm()
    
    if form.validate_on_submit():
        user = User.query.get(session['user_id'])
        auth_service = AuthService(user_repository=None)
        
        # Check the code
        if auth_service.verify_totp(user, form.code.data):
            login_user(user, remember=session.get('remember_me', False))
            next_page = session.get('next_page') or url_for('dashboard.index')
            
            # Clean up session
            session.pop('user_id', None)
            session.pop('remember_me', None)
            session.pop('next_page', None)
            
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = request.remote_addr
            db.session.commit()
            
            return redirect(next_page)
            
        flash('Invalid verification code. Please try again.', 'error')
    
    return render_template('auth/two_factor_verify.html', form=form)

@auth_bp.route('/security', methods=['GET'])
@login_required
def security_settings():
    """User security settings page"""
    change_password_form = ChangePasswordForm()
    return render_template('auth/security.html', change_password_form=change_password_form)

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Handle password change requests"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('auth.security_settings'))
            
        if form.new_password.data != form.confirm_password.data:
            flash('New passwords do not match', 'error')
            return redirect(url_for('auth.security_settings'))
            
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been updated', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'error')
                
    return redirect(url_for('auth.security_settings'))

@auth_bp.route('/send-verification-email', methods=['POST'])
@login_required
def send_verification_email():
    """Send email verification link to user"""
    auth_service = container.get('auth_service')
    
    # Generate a new token
    token = auth_service.generate_email_verification_token(current_user)
    
    # Create verification link
    verification_link = url_for('auth.verify_email', token=token, _external=True)
    
    # Send verification email
    email_sent = auth_service.email_service.send_verification_email(current_user, verification_link)
    
    if email_sent:
        flash('Verification email sent. Please check your inbox.', 'success')
    else:
        flash('Failed to send verification email. Please try again later.', 'error')
        
    return redirect(url_for('auth.security_settings'))

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address using token"""
    auth_service = container.get('auth_service')
    
    success, message = auth_service.verify_email(token)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    if current_user.is_authenticated:
        return redirect(url_for('auth.security_settings'))
    else:
        return redirect(url_for('auth.login'))

# Passkey (WebAuthn) routes
@auth_bp.route('/passkeys')
@login_required
def passkeys():
    """Display user's passkeys"""
    return render_template('auth/passkeys.html')

@auth_bp.route('/passkeys/register/options', methods=['POST'])
@login_required
def passkey_register_options():
    """Get registration options for a new passkey"""
    passkey_service = PasskeyService(user_repository=container.get('user_repository'))
    
    options = passkey_service.start_registration(current_user)
    if options:
        return jsonify(json.loads(options))
    else:
        return jsonify({"error": "Failed to generate registration options"}), 500

@auth_bp.route('/passkeys/register/verify', methods=['POST'])
@login_required
def passkey_register_verify():
    """Verify and complete passkey registration"""
    passkey_service = PasskeyService(user_repository=container.get('user_repository'))
    
    credential_data = request.json
    success, message = passkey_service.complete_registration(current_user, credential_data)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message}), 400

@auth_bp.route('/passkeys/authenticate/options', methods=['POST'])
def passkey_authenticate_options():
    """Get authentication options for passkey login"""
    passkey_service = PasskeyService(user_repository=container.get('user_repository'))
    
    options = passkey_service.start_authentication()
    if options:
        return jsonify(json.loads(options))
    else:
        return jsonify({"error": "Failed to generate authentication options"}), 500

@auth_bp.route('/passkeys/authenticate/verify', methods=['POST'])
def passkey_authenticate_verify():
    """Verify passkey authentication and log user in"""
    passkey_service = PasskeyService(user_repository=container.get('user_repository'))
    
    credential_data = request.json
    success, result = passkey_service.verify_authentication(credential_data)
    
    if success:
        # User verification passed
        return jsonify({"success": True})
        
    elif isinstance(result, str) and len(result) > 0:
        # We got a credential ID, try to find the user
        user = passkey_service.find_user_by_credential_id(result)
        
        if user:
            # Try to verify again with the user
            success, _ = passkey_service.verify_authentication(credential_data, user)
            
            if success:
                login_user(user)
                user.last_login_at = datetime.utcnow()
                user.last_login_ip = request.remote_addr
                db.session.commit()
                return jsonify({
                    "success": True, 
                    "redirect": url_for('dashboard.index')
                })
    
    return jsonify({"success": False, "error": "Authentication failed"}), 400

@auth_bp.route('/passkeys/delete/<credential_id>', methods=['POST'])
@login_required
def passkey_delete(credential_id):
    """Delete a passkey"""
    passkey_service = PasskeyService(user_repository=container.get('user_repository'))
    
    success, message = passkey_service.delete_passkey(current_user, credential_id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        
    return redirect(url_for('auth.passkeys'))
