import logging
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for, request,
    flash, session, current_app, jsonify
)
from flask_login import (
    login_user, logout_user, login_required, current_user
)
from app.extensions import db, limiter
from app.models.user import User, Role
from app.models.user_repository import SqlAlchemyUserRepository
from app.auth.forms import (
    LoginForm, RegistrationForm, RequestPasswordResetForm,
    ResetPasswordForm, TOTPSetupForm, TOTPVerifyForm, ChangePasswordForm
)
from app.auth.totp import (
    generate_totp_secret, get_totp_uri, 
    verify_totp, generate_qr_code_data_uri
)
from app.auth.webauthn import (
    create_webauthn_registration_options, verify_webauthn_registration,
    create_webauthn_authentication_options, verify_webauthn_authentication
)
from app.utils.email import send_password_reset_email, send_verification_email

import uuid
import secrets
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__)
log = logging.getLogger(__name__)
user_repository = SqlAlchemyUserRepository(db)

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = user_repository.get_by_email(form.email.data.lower())
        
        if user and check_password_hash(user.password_hash, form.password.data):
            # Check if 2FA is enabled
            if user.is_totp_enabled:
                # Store user ID in session for 2FA verification
                session['totp_user_id'] = user.id
                return redirect(url_for('auth.verify_totp'))
            else:
                # Login successful
                login_user(user, remember=form.remember_me.data)
                
                # Update last login info
                user.last_login_at = datetime.utcnow()
                user.last_login_ip = request.remote_addr
                db.session.commit()
                
                # Log the event
                user_repository.add_audit_log(
                    user_id=user.id,
                    action='login',
                    details="User logged in",
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
                
                # Redirect to requested page or home
                next_page = request.args.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('home.index')
                return redirect(next_page)
        else:
            # Login failed
            flash('Invalid email or password', 'error')
            
            # Log failed login attempt
            if user:
                user_repository.add_audit_log(
                    user_id=user.id,
                    action='login_failed',
                    details="Failed login attempt",
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
            else:
                # Log attempt with non-existent user
                user_repository.add_audit_log(
                    user_id=None,
                    action='login_failed',
                    details=f"Failed login attempt with email {form.email.data}",
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
    
    return render_template('auth/login.html', form=form)

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if user_repository.get_by_username(form.username.data):
            flash('Username already taken', 'error')
            return render_template('auth/register.html', form=form)
            
        if user_repository.get_by_email(form.email.data.lower()):
            flash('Email already registered', 'error')
            return render_template('auth/register.html', form=form)
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            username=form.username.data,
            email=form.email.data.lower(),
            password_hash=generate_password_hash(form.password.data),
            role=Role.USER.value,
            verification_token=secrets.token_urlsafe(32),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Save the user
        user_repository.save(user)
        
        # Send verification email
        send_verification_email(user)
        
        flash('Registration successful! Please check your email to verify your account.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html', form=form)

@auth_bp.route("/logout")
def logout():
    """Log out the current user."""
    if current_user.is_authenticated:
        user_id = current_user.id
        
        # Log the event before logout
        user_repository.add_audit_log(
            user_id=user_id,
            action='logout',
            details="User logged out",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
    
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('home.index'))

@auth_bp.route("/verify/<token>")
@limiter.limit("10 per minute")
def verify_email(token):
    """Verify email with token."""
    user = user_repository.get_by_verification_token(token)
    
    if user is None:
        flash("Invalid or expired verification token.", "error")
        return redirect(url_for("auth.login"))
        
    user.is_active = True
    user.email_verification_token = None
    user_repository.update(user)
    
    flash("Your email address has been verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def resend_verification():
    """Resend email verification."""
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return render_template('auth/resend_verification.html')
        
        user = user_repository.get_by_email(email.lower())
        
        if not user:
            # Don't reveal if email exists
            flash('If your email exists in our system, a verification link has been sent.', 'info')
            return redirect(url_for('auth.login'))
        
        if user.email_verified_at:
            # Email already verified
            flash('Your email is already verified. You can log in.', 'info')
            return redirect(url_for('auth.login'))
        
        # Generate new token if needed
        if not user.verification_token:
            user.verification_token = secrets.token_urlsafe(32)
            user_repository.save(user)
        
        # Send verification email
        send_verification_email(user)
        
        flash('If your email exists in our system, a verification link has been sent.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/resend_verification.html')

@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password_request():
    """Request password reset."""
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))
        
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        user = user_repository.get_by_email(form.email.data.lower())
        
        if user:
            # Generate reset token
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
            user_repository.save(user)
            
            # Send reset email
            send_password_reset_email(user)
            
            # Log the event
            user_repository.add_audit_log(
                user_id=user.id,
                action='password_reset_requested',
                details="Password reset requested",
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
        
        # Don't reveal if email exists
        flash('If your email exists in our system, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password_request.html', form=form)

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password(token):
    """Reset password with token."""
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))
        
    user = user_repository.get_by_reset_token(token)
    
    # Check if token is valid and not expired
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        flash('Invalid or expired password reset link', 'error')
        return redirect(url_for('auth.reset_password_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Update password
        user.password_hash = generate_password_hash(form.password.data)
        user.reset_token = None
        user.reset_token_expires_at = None
        user.updated_at = datetime.utcnow()
        user_repository.save(user)
        
        # Log the event
        user_repository.add_audit_log(
            user_id=user.id,
            action='password_reset_completed',
            details="Password reset completed",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash('Your password has been reset successfully.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', form=form)

@auth_bp.route("/verify-totp", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def verify_totp():
    """Verify TOTP 2FA code during login."""
    if 'totp_user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = user_repository.get_by_id(session['totp_user_id'])
    if not user:
        session.pop('totp_user_id', None)
        flash('Invalid session', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        totp_code = request.form.get('totp_code')
        
        if not totp_code:
            flash('Verification code is required', 'error')
            return render_template('auth/verify_totp.html')
            
        if verify_totp(user.totp_secret, totp_code):
            # TOTP verification successful
            # Clean up session
            session.pop('totp_user_id', None)
            
            # Log in the user
            login_user(user)
            
            # Update last login info
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = request.remote_addr
            db.session.commit()
            
            # Log the event
            user_repository.add_audit_log(
                user_id=user.id,
                action='login_2fa',
                details="User logged in with 2FA",
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            
            # Redirect to requested page or home
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('home.index')
            return redirect(next_page)
        else:
            # Invalid TOTP code
            flash('Invalid verification code', 'error')
            
            # Log failed attempt
            user_repository.add_audit_log(
                user_id=user.id,
                action='login_2fa_failed',
                details="Failed 2FA verification",
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
    
    return render_template('auth/verify_totp.html')

@auth_bp.route("/setup-totp", methods=["GET", "POST"])
@login_required
def setup_totp():
    """Set up TOTP 2FA for a user."""
    # Check if TOTP is already set up
    if current_user.is_totp_enabled:
        flash("Two-factor authentication is already enabled for your account.", "info")
        return redirect(url_for("auth.security_settings"))
        
    # Generate a new TOTP secret if not already in session
    if "totp_setup_secret" not in session:
        session["totp_setup_secret"] = generate_totp_secret()
        
    secret = session["totp_setup_secret"]
    totp_uri = get_totp_uri(current_user, secret)
    qr_code = generate_qr_code_data_uri(totp_uri)
    
    form = TOTPSetupForm()
    if form.validate_on_submit():
        if verify_totp(secret, form.token.data):
            # TOTP verification successful, save the secret
            current_user.totp_secret = secret
            current_user.is_totp_enabled = True
            user_repository.update(current_user)
            
            # Clear TOTP setup session data
            session.pop("totp_setup_secret", None)
            
            flash("Two-factor authentication has been enabled for your account.", "success")
            return redirect(url_for("auth.security_settings"))
        else:
            flash("Invalid verification code. Please try again.", "error")
            
    return render_template(
        "auth/setup_totp.html",
        form=form,
        qr_code=qr_code,
        secret=secret
    )

@auth_bp.route("/disable-totp", methods=["POST"])
@login_required
def disable_totp():
    """Disable TOTP 2FA for a user."""
    if not current_user.is_totp_enabled:
        flash("Two-factor authentication is not enabled for your account.", "info")
        return redirect(url_for("auth.security_settings"))
        
    current_user.is_totp_enabled = False
    current_user.totp_secret = None
    user_repository.update(current_user)
    
    flash("Two-factor authentication has been disabled for your account.", "success")
    return redirect(url_for("auth.security_settings"))

@auth_bp.route("/webauthn-login", methods=["GET"])
@limiter.limit("10 per minute")
def webauthn_login():
    """WebAuthn authentication page."""
    # Ensure there's a user in the session waiting for WebAuthn
    if "webauthn_auth_user_id" not in session:
        return redirect(url_for("auth.login"))
        
    user = user_repository.get_by_id(session["webauthn_auth_user_id"])
    if not user:
        session.pop("webauthn_auth_user_id")
        return redirect(url_for("auth.login"))
        
    return render_template("auth/webauthn_login.html", username=user.username)

@auth_bp.route("/webauthn-login/options", methods=["POST"])
@limiter.limit("10 per minute")
def webauthn_login_options():
    """Get WebAuthn authentication options."""
    # Ensure there's a user in the session waiting for WebAuthn
    if "webauthn_auth_user_id" not in session:
        return jsonify({"error": "No authentication in progress"}), 400
        
    user = user_repository.get_by_id(session["webauthn_auth_user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    options_json = create_webauthn_authentication_options(user)
    return jsonify(json.loads(options_json))

@auth_bp.route("/webauthn-login/verify", methods=["POST"])
@limiter.limit("10 per minute")
def webauthn_login_verify():
    """Verify WebAuthn authentication."""
    try:
        data = request.get_json()
        success, user, error_msg = verify_webauthn_authentication(data)
        
        if not success:
            return jsonify({"verified": False, "error": error_msg}), 400
            
        login_user(user)
        user.record_login_attempt(True, request.remote_addr)
        user_repository.update(user)
        
        # Clear WebAuthn session data
        session.pop("webauthn_auth_user_id", None)
        
        return jsonify({
            "verified": True,
            "redirectUrl": url_for("home.index")
        })
    except Exception as e:
        log.error(f"WebAuthn verification error: {str(e)}")
        return jsonify({"verified": False, "error": str(e)}), 500

@auth_bp.route("/security", methods=["GET"])
@login_required
def security_settings():
    """Security settings page."""
    credentials = user_repository.get_credentials_by_user_id(current_user.id)
    return render_template(
        "auth/security_settings.html",
        user=current_user,
        credentials=credentials
    )

@auth_bp.route("/setup-webauthn", methods=["GET"])
@login_required
def setup_webauthn():
    """Set up WebAuthn for a user."""
    return render_template("auth/setup_webauthn.html")

@auth_bp.route("/setup-webauthn/options", methods=["POST"])
@login_required
def setup_webauthn_options():
    """Get WebAuthn registration options."""
    options_json = create_webauthn_registration_options(current_user)
    return jsonify(json.loads(options_json))

@auth_bp.route("/setup-webauthn/verify", methods=["POST"])
@login_required
def setup_webauthn_verify():
    """Verify WebAuthn registration."""
    try:
        data = request.get_json()
        credential_name = request.args.get("name", "")
        
        success, result = verify_webauthn_registration(data, credential_name)
        
        if not success:
            return jsonify({"registered": False, "error": str(result)}), 400
            
        return jsonify({
            "registered": True,
            "credentialId": result.credential_id
        })
    except Exception as e:
        log.error(f"WebAuthn registration error: {str(e)}")
        return jsonify({"registered": False, "error": str(e)}), 500

@auth_bp.route("/remove-webauthn/<credential_id>", methods=["POST"])
@login_required
def remove_webauthn(credential_id):
    """Remove a WebAuthn credential."""
    credential = user_repository.get_credential_by_id(credential_id)
    
    if not credential or credential.user_id != current_user.id:
        flash("Credential not found.", "error")
        return redirect(url_for("auth.security_settings"))
        
    user_repository.delete_credential(credential)
    
    # If user has no more credentials, disable WebAuthn
    remaining = user_repository.get_credentials_by_user_id(current_user.id)
    if not remaining:
        current_user.is_webauthn_enabled = False
        user_repository.update(current_user)
        
    flash("Passkey has been removed successfully.", "success")
    return redirect(url_for("auth.security_settings"))

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change user password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "error")
            return render_template("auth/change_password.html", form=form)
            
        current_user.set_password(form.new_password.data)
        user_repository.update(current_user)
        
        flash("Your password has been updated.", "success")
        return redirect(url_for("auth.security_settings"))
        
    return render_template("auth/change_password.html", form=form)
