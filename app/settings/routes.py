"""Routes for application settings."""

from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user, logout_user
from app.settings.forms import SyncSettingsForm, EmailSettingsForm, ProfileForm, ChangePasswordForm, AccountSettingsForm
from app.services.container import container
from app.models.user import User
from app.models.account import Account
from app.extensions import db
import json

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@login_required
def index():
    """Settings index page."""
    return render_template('settings/index.html', title='Settings')

@settings_bp.route('/sync', methods=['GET', 'POST'])
@login_required
def sync_settings():
    """Synchronization settings page."""
    # Get service container
    setting_repository = container().get('setting_repository')
    
    # Get current settings
    settings_key = f'sync_settings:{current_user.id}'
    settings_json = setting_repository.get(settings_key)
    
    try:
        current_settings = json.loads(settings_json) if settings_json else {}
    except json.JSONDecodeError:
        current_settings = {}
    
    # Create form with current values
    form = SyncSettingsForm(
        enable_sync=current_settings.get('enable_sync', True),
        sync_interval=current_settings.get('sync_interval', 2),
        enable_cooldown=current_settings.get('enable_cooldown', True),
        cooldown_hours=current_settings.get('cooldown_hours', 3)
    )
    
    if form.validate_on_submit():
        # Save settings
        new_settings = {
            'enable_sync': form.enable_sync.data,
            'sync_interval': form.sync_interval.data,
            'enable_cooldown': form.enable_cooldown.data,
            'cooldown_hours': form.cooldown_hours.data
        }
        
        # Save to repository
        setting_repository.save_setting(settings_key, json.dumps(new_settings))
        
        # Update scheduler
        scheduler_service = container().get('scheduler_service')
        if scheduler_service:
            scheduler_service.update_sync_schedule(current_user.id)
        
        flash('Synchronization settings updated successfully!', 'success')
        return redirect(url_for('settings.index'))
    
    return render_template('settings/sync_settings.html', 
                          title='Synchronization Settings',
                          form=form)

@settings_bp.route('/email', methods=['GET', 'POST'])
@login_required
def email_settings():
    """Email settings page."""
    # Only allow admins to change email settings
    if not current_user.is_admin:
        flash('You do not have permission to access email settings.', 'error')
        return redirect(url_for('settings.index'))
        
    # Get service container
    setting_repository = container().get('setting_repository')
    
    # Get current settings
    smtp_server = setting_repository.get('smtp_server', '')
    smtp_port = setting_repository.get('smtp_port', 587)
    try:
        smtp_port = int(smtp_port)
    except (ValueError, TypeError):
        smtp_port = 587
        
    smtp_username = setting_repository.get('smtp_username', '')
    smtp_use_tls = setting_repository.get('smtp_use_tls', 'true').lower() == 'true'
    default_sender = setting_repository.get('mail_default_sender', '')
    
    # Create form with current values
    form = EmailSettingsForm(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_use_tls=smtp_use_tls,
        default_sender=default_sender
    )
    
    if form.validate_on_submit():
        # Save settings
        setting_repository.save_setting('smtp_server', form.smtp_server.data)
        setting_repository.save_setting('smtp_port', str(form.smtp_port.data))
        setting_repository.save_setting('smtp_username', form.smtp_username.data)
        setting_repository.save_setting('smtp_use_tls', str(form.smtp_use_tls.data).lower())
        setting_repository.save_setting('mail_default_sender', form.default_sender.data)
        
        # Only update password if provided
        if form.smtp_password.data:
            setting_repository.save_setting('smtp_password', form.smtp_password.data)
        
        # Update mail configuration
        if hasattr(current_app, 'extensions') and 'mail' in current_app.extensions:
            mail = current_app.extensions['mail']
            mail.server = form.smtp_server.data
            mail.port = form.smtp_port.data
            mail.username = form.smtp_username.data
            mail.use_tls = form.smtp_use_tls.data
            if form.smtp_password.data:
                mail.password = form.smtp_password.data
            mail.default_sender = form.default_sender.data
        
        flash('Email settings updated successfully!', 'success')
        return redirect(url_for('settings.index'))
    
    return render_template('settings/email_settings.html', 
                          title='Email Settings',
                          form=form)

@settings_bp.route('/email/test', methods=['POST'])
@login_required
def test_email():
    """Send a test email to verify configuration."""
    # Only allow admins to send test emails
    if not current_user.is_admin:
        flash('You do not have permission to send test emails.', 'error')
        return redirect(url_for('settings.index'))
    
    # Get email service
    email_service = container().get('email_service')
    
    if not email_service:
        flash('Email service is not available.', 'error')
        return redirect(url_for('settings.email_settings'))
    
    try:
        # Send test email to current user
        result = email_service.send_email(
            subject="Test Email from Monzo Credit Card Pot Sync",
            recipients=[current_user.email],
            body="This is a test email to verify your email configuration is working correctly.",
            html="<p>This is a test email to verify your email configuration is working correctly.</p>"
        )
        
        if result:
            flash('Test email sent successfully! Please check your inbox.', 'success')
        else:
            flash('Failed to send test email. Please check your configuration.', 'error')
    except Exception as e:
        flash(f'Error sending test email: {str(e)}', 'error')
    
    return redirect(url_for('settings.email_settings'))

@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile settings page."""
    form = ProfileForm(
        username=current_user.username,
        email=current_user.email
    )
    
    password_form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Check if username is taken by another user
        existing_user = User.query.filter(
            User.username == form.username.data,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            flash('Username already taken.', 'error')
            return render_template('settings/profile.html', 
                                  title='Profile Settings',
                                  form=form,
                                  password_form=password_form)
        
        # Check if email is taken by another user
        existing_user = User.query.filter(
            User.email == form.email.data,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            flash('Email already registered.', 'error')
            return render_template('settings/profile.html', 
                                  title='Profile Settings',
                                  form=form,
                                  password_form=password_form)
        
        # Update user profile
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('settings.profile'))
    
    return render_template('settings/profile.html', 
                          title='Profile Settings',
                          form=form,
                          password_form=password_form)

@settings_bp.route('/password', methods=['POST'])
@login_required
def change_password():
    """Change user password."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('settings.profile'))
        
        # Update password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('settings.profile'))
    
    # If form validation failed
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'error')
    
    return redirect(url_for('settings.profile'))

@settings_bp.route('/account/<int:account_id>', methods=['GET', 'POST'])
@login_required
def account_settings(account_id):
    """Account settings page."""
    account = Account.query.filter_by(
        id=account_id, user_id=current_user.id
    ).first_or_404()
    
    form = AccountSettingsForm(
        name=account.name
    )
    
    if form.validate_on_submit():
        # Update account settings
        account.name = form.name.data
        db.session.commit()
        
        flash('Account settings updated successfully!', 'success')
        return redirect(url_for('accounts.manage'))
    
    return render_template('settings/account_settings.html', 
                          title='Account Settings',
                          form=form,
                          account=account)

@settings_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account."""
    confirmation = request.form.get('confirm', '').strip()
    
    if confirmation != 'DELETE':
        flash('Please type DELETE to confirm account deletion.', 'error')
        return redirect(url_for('settings.profile'))
    
    try:
        # Delete all user's accounts and data
        Account.query.filter_by(user_id=current_user.id).delete()
        db.session.delete(current_user)
        db.session.commit()
        
        # Log the user out
        logout_user()
        
        flash('Your account has been deleted successfully.', 'success')
        return redirect(url_for('main.index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'error')
        return redirect(url_for('settings.profile'))

@settings_bp.route('/notifications', methods=['POST'])
@login_required
def update_notifications():
    """Update notification settings."""
    setting_repository = container().get('setting_repository')
    email_enabled = 'email_notifications' in request.form
    
    # Save user's notification preferences
    settings_key = f'notification_settings:{current_user.id}'
    settings = {
        'email_enabled': email_enabled
    }
    
    setting_repository.save_setting(settings_key, json.dumps(settings))
    flash('Notification preferences updated.', 'success')
    
    return redirect(url_for('dashboard.index'))

@settings_bp.route('/notifications', methods=['GET'])
@login_required
def notifications():
    """Notification settings page."""
    setting_repository = container().get('setting_repository')
    settings_key = f'notification_settings:{current_user.id}'
    settings_json = setting_repository.get(settings_key)
    
    try:
        settings = json.loads(settings_json) if settings_json else {}
    except json.JSONDecodeError:
        settings = {}
        
    email_settings = {
        'email_enabled': settings.get('email_enabled', False)
    }
    
    return render_template('settings/notifications.html',
                          title='Notification Settings',
                          settings=email_settings)
