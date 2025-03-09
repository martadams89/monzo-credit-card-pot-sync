"""Routes for authentication."""

import logging
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, abort
from flask_login import login_user, logout_user, current_user, login_required
from app.auth.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from app.models.user import User
from app.extensions import db
from app.services.container import container
from app.utils.error_handler import handle_error

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user is None:
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html', title='Sign In', form=form)
            
        if not user.check_password(form.password.data):
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html', title='Sign In', form=form)
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'error')
            return render_template('auth/login.html', title='Sign In', form=form)
            
        # Log in user
        login_user(user, remember=form.remember_me.data)
        
        # Record login in activity log
        try:
            history_repo = container().get('history_repository')
            if history_repo:
                history_repo.save_activity(user.id, 'login', {
                    'ip': request.remote_addr,
                    'user_agent': request.user_agent.string
                })
        except Exception as e:
            logger.error(f"Error recording login activity: {str(e)}")
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard.index')
        return redirect(next_page)
        
    return render_template('auth/login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
def logout():
    """Logout route."""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Check if registration is enabled
    setting_repository = container().get('setting_repository')
    allow_registration = setting_repository.get('allow_registration', 'true').lower() in ('true', 'yes', '1')
    
    if not allow_registration:
        flash('Registration is currently disabled. Please contact an administrator.', 'error')
        return redirect(url_for('auth.login'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            # Create user
            user = User(
                username=form.username.data,
                email=form.email.data,
                is_active=True,
                created_at=datetime.utcnow()
            )
            user.set_password(form.password.data)
            
            # Make first user an admin
            user_count = User.query.count()
            if user_count == 0:
                user.is_admin = True
                flash('As the first user, you have been granted administrator privileges.', 'info')
            
            # Save user
            db.session.add(user)
            db.session.commit()
            
            # Send welcome email
            try:
                email_service = container().get('email_service')
                if email_service:
                    email_service.send_template_email(
                        subject="Welcome to Monzo Credit Card Pot Sync",
                        recipients=[user.email],
                        template="welcome",
                        context={"user": user}
                    )
            except Exception as e:
                logger.error(f"Error sending welcome email: {str(e)}")
            
            flash('Your account has been created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
    
    return render_template('auth/register.html', title='Register', form=form)

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # Generate token
            auth_service = container().get('auth_service')
            token = auth_service.generate_reset_token(user)
            
            # Send reset email
            email_service = container().get('email_service')
            if email_service:
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                
                email_service.send_template_email(
                    subject="Password Reset Request",
                    recipients=[user.email],
                    template="password_reset",
                    context={"user": user, "reset_url": reset_url}
                )
                
            flash('Check your email for instructions to reset your password.', 'info')
        else:
            # Don't reveal that email doesn't exist for security
            flash('Check your email for instructions to reset your password.', 'info')
            
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password_request.html', title='Reset Password', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    # Verify token
    auth_service = container().get('auth_service')
    user = auth_service.verify_reset_token(token)
    
    if not user:
        flash('Invalid or expired reset link. Please try again.', 'error')
        return redirect(url_for('auth.reset_password_request'))
        
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', title='Reset Password', form=form)

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page."""
    return render_template('auth/profile.html', title='Your Profile')

@auth_bp.route('/security')
@login_required
def security():
    """User security settings page."""
    return render_template('auth/security.html', title='Security Settings')

@auth_bp.route('/passkeys')
@login_required
def passkeys():
    """User passkey management page."""
    return render_template('auth/passkeys.html', title='Manage Passkeys')

@auth_bp.route('/passkeys/register/options', methods=['POST'])
@login_required
def passkeys_register_options():
    """Get options for registering a new passkey."""
    try:
        # Get WebAuthn service
        webauthn_service = container().get('webauthn_service')
        
        if not webauthn_service:
            return jsonify({'error': 'WebAuthn service is not available'}), 500
        
        # Get registration options
        registration_options = webauthn_service.generate_registration_options(current_user.id)
        
        # Store challenge in session for verification
        session['passkey_challenge'] = registration_options['challenge']
        
        return jsonify(registration_options)
    
    except Exception as e:
        current_app.logger.error(f"Error generating passkey registration options: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/passkeys/register/verify', methods=['POST'])
@login_required
def passkeys_register_verify():
    """Verify and register a new passkey."""
    try:
        # Get WebAuthn service
        webauthn_service = container().get('webauthn_service')
        
        if not webauthn_service:
            return jsonify({'error': 'WebAuthn service is not available'}), 500
        
        # Get challenge from session
        challenge = session.pop('passkey_challenge', None)
        
        if not challenge:
            return jsonify({'error': 'Invalid or expired registration session'}), 400
        
        # Verify the registration
        credential_data = request.json
        passkey_id = webauthn_service.verify_registration(credential_data, challenge, current_user.id)
        
        if not passkey_id:
            return jsonify({'error': 'Failed to verify passkey'}), 400
        
        # Store passkey for user
        current_user.add_passkey(passkey_id)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        current_app.logger.error(f"Error verifying passkey registration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/passkeys/authenticate/options', methods=['POST'])
def passkeys_authenticate_options():
    """Get options for authenticating with a passkey."""
    try:
        # Get WebAuthn service
        webauthn_service = container().get('webauthn_service')
        
        if not webauthn_service:
            return jsonify({'error': 'WebAuthn service is not available'}), 500
        
        # Generate authentication options
        auth_options = webauthn_service.generate_authentication_options()
        
        # Store challenge in session for verification
        session['passkey_auth_challenge'] = auth_options['challenge']
        
        return jsonify(auth_options)
    
    except Exception as e:
        current_app.logger.error(f"Error generating passkey authentication options: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/passkeys/authenticate/verify', methods=['POST'])
def passkeys_authenticate_verify():
    """Verify passkey authentication and log in the user."""
    try:
        # Get WebAuthn service
        webauthn_service = container().get('webauthn_service')
        
        if not webauthn_service:
            return jsonify({'error': 'WebAuthn service is not available'}), 500
        
        # Get challenge from session
        challenge = session.pop('passkey_auth_challenge', None)
        
        if not challenge:
            return jsonify({'error': 'Invalid or expired authentication session'}), 400
        
        # Verify the authentication
        credential_data = request.json
        user_id = webauthn_service.verify_authentication(credential_data, challenge)
        
        if not user_id:
            return jsonify({'error': 'Authentication failed'}), 401
        
        # Get user by passkey
        user = User.query.filter_by(id=user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user is active
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        # Login the user
        login_user(user)
        
        # Update last login time
        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'redirect': url_for('dashboard.index')
        })
    
    except Exception as e:
        current_app.logger.error(f"Error authenticating with passkey: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/oauth/monzo/callback')
def monzo_callback():
    """Handle Monzo OAuth callback."""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code or not state:
        flash('Authorization failed: Missing parameters', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Get services
    auth_service = container().get('auth_service')
    
    if not auth_service:
        flash('Service unavailable', 'error')
        return redirect(url_for('accounts.connect'))
    
    try:
        # Verify state to prevent CSRF
        if not auth_service.verify_oauth_state(state):
            flash('Invalid authorization state', 'error')
            return redirect(url_for('accounts.connect'))
        
        # Exchange code for tokens
        user_id = current_user.id if current_user.is_authenticated else None
        success = auth_service.complete_monzo_auth(code, user_id)
        
        if success:
            flash('Monzo account connected successfully!', 'success')
            return redirect(url_for('accounts.manage'))
        else:
            flash('Failed to connect Monzo account', 'error')
            return redirect(url_for('accounts.connect'))
    except Exception as e:
        flash(f'Error connecting Monzo account: {str(e)}', 'error')
        return redirect(url_for('accounts.connect'))

@auth_bp.route('/oauth/truelayer/callback')
def truelayer_callback():
    """Handle TrueLayer OAuth callback for credit card accounts."""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code or not state:
        flash('Authorization failed: Missing parameters', 'error')
        return redirect(url_for('accounts.connect'))
    
    # Get services
    auth_service = container().get('auth_service')
    
    if not auth_service:
        flash('Service unavailable', 'error')
        return redirect(url_for('accounts.connect'))
    
    try:
        # Verify state to prevent CSRF
        if not auth_service.verify_oauth_state(state):
            flash('Invalid authorization state', 'error')
            return redirect(url_for('accounts.connect'))
        
        # Exchange code for tokens
        user_id = current_user.id if current_user.is_authenticated else None
        success = auth_service.complete_truelayer_auth(code, user_id)
        
        if success:
            flash('Credit card connected successfully!', 'success')
            return redirect(url_for('accounts.manage'))
        else:
            flash('Failed to connect credit card', 'error')
            return redirect(url_for('accounts.connect'))
    except Exception as e:
        flash(f'Error connecting credit card: {str(e)}', 'error')
        return redirect(url_for('accounts.connect'))
