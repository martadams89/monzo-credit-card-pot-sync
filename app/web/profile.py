import logging
import uuid
import secrets
from datetime import datetime, timedelta
import csv
from io import StringIO

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.user import User, LoginSession
from app.models.audit import AuditLog
from app.models.monzo import MonzoAccount
from app.models.api_key import ApiKey

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")
log = logging.getLogger(__name__)

@profile_bp.before_request
@login_required
def before_request():
    """Ensure all profile routes are protected."""
    pass

@profile_bp.route("/")
def index():
    """User profile home page."""
    # Get user's connected accounts
    accounts = MonzoAccount.query.filter_by(user_id=current_user.id).all()
    
    # Get recent activity logs
    recent_activity = AuditLog.query.filter_by(
        user_id=current_user.id
    ).order_by(AuditLog.created_at.desc()).limit(5).all()
    
    return render_template(
        'profile/index.html',
        accounts=accounts,
        recent_activity=recent_activity
    )

@profile_bp.route("/edit", methods=['GET', 'POST'])
def edit():
    """Edit user profile."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        
        # Validate inputs
        if not username or not email or not current_password:
            flash('All fields are required', 'error')
            return redirect(url_for('profile.edit'))
        
        # Verify current password
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('profile.edit'))
        
        # Check if username is being changed and is already taken
        if username != current_user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username is already taken', 'error')
                return redirect(url_for('profile.edit'))
        
        # Check if email is being changed and is already taken
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email is already taken', 'error')
                return redirect(url_for('profile.edit'))
        
        # Update user profile
        changes = []
        if username != current_user.username:
            changes.append(f"Username changed from '{current_user.username}' to '{username}'")
            current_user.username = username
        
        if email != current_user.email:
            changes.append(f"Email changed from '{current_user.email}' to '{email}'")
            current_user.email = email
            
            # If email changed, require verification again
            current_user.is_email_verified = False
            current_user.email_verification_token = str(uuid.uuid4())
            
            # Here you would send verification email
            # send_verification_email(current_user)
            
            changes.append("Email verification status reset")
        
        # Update timestamp
        current_user.updated_at = datetime.utcnow()
        
        # Log the changes
        if changes:
            audit_log = AuditLog(
                user_id=current_user.id,
                action="profile_update",
                details="; ".join(changes),
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
        
        db.session.commit()
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile.index'))
    
    return render_template('profile/edit.html')

@profile_bp.route("/delete-account", methods=['GET', 'POST'])
def delete_account():
    """Show delete account confirmation page."""
    return render_template('profile/delete_account.html')

@profile_bp.route("/delete-account-confirm", methods=['POST'])
def delete_account_confirm():
    """Process account deletion."""
    password = request.form.get('password')
    confirm_delete = 'confirm_delete' in request.form
    
    if not password or not confirm_delete:
        flash('Please confirm your password and check the confirmation box', 'error')
        return redirect(url_for('profile.delete_account'))
    
    # Verify password
    if not check_password_hash(current_user.password_hash, password):
        flash('Password is incorrect', 'error')
        return redirect(url_for('profile.delete_account'))
    
    # Record the deletion event before deleting the user
    user_id = current_user.id
    username = current_user.username
    email = current_user.email
    ip_address = request.remote_addr
    
    try:
        # Deactivate account first
        current_user.is_active = False
        db.session.commit()
        
        # Log action in admin audit log
        admin_audit = AuditLog(
            action="account_deleted",
            details=f"User {username} ({email}) deleted their account",
            ip_address=ip_address,
            user_id=user_id
        )
        db.session.add(admin_audit)
        db.session.commit()
        
        # Then perform logout
        from flask_login import logout_user
        logout_user()
        
        flash('Your account has been successfully deleted', 'success')
        return redirect(url_for('home.index'))
    except Exception as e:
        db.session.rollback()
        log.error(f"Error deleting account: {str(e)}")
        flash('An error occurred while deleting your account. Please try again later.', 'error')
        return redirect(url_for('profile.delete_account'))

@profile_bp.route("/sessions")
def sessions():
    """View active login sessions."""
    # Get the current session
    current_session = LoginSession.query.filter_by(
        user_id=current_user.id,
        is_active=True,
        session_id=request.cookies.get('session')
    ).first()
    
    # Get other active sessions
    other_sessions = LoginSession.query.filter(
        LoginSession.user_id == current_user.id,
        LoginSession.is_active == True,
        LoginSession.session_id != request.cookies.get('session')
    ).all()
    
    return render_template(
        'profile/sessions.html',
        current_session=current_session,
        other_sessions=other_sessions
    )

@profile_bp.route("/revoke-session/<session_id>", methods=['POST'])
def revoke_session(session_id):
    """Revoke a specific session."""
    session = LoginSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    session.is_active = False
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="session_revoked",
        details=f"Session from {session.device_info or 'Unknown device'} revoked",
        ip_address=request.remote_addr
    )
    db.session.add(audit_log)
    db.session.commit()
    
    flash('Session has been successfully signed out', 'success')
    return redirect(url_for('profile.sessions'))

@profile_bp.route("/revoke-all-sessions", methods=['POST'])
def revoke_all_sessions():
    """Revoke all sessions except the current one."""
    # Update all sessions except current one
    db.session.query(LoginSession).filter(
        LoginSession.user_id == current_user.id,
        LoginSession.is_active == True,
        LoginSession.session_id != request.cookies.get('session')
    ).update({
        'is_active': False
    })
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="all_sessions_revoked",
        details="All other sessions were signed out",
        ip_address=request.remote_addr
    )
    db.session.add(audit_log)
    db.session.commit()
    
    flash('All other devices have been signed out', 'success')
    return redirect(url_for('profile.sessions'))

@profile_bp.route("/activity-log")
def activity_log():
    """View user activity log with filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get filter parameters
    action = request.args.get('action')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    query = AuditLog.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action)
        
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= start_date)
        except ValueError:
            flash('Invalid start date format', 'error')
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            # Make it inclusive of the entire day
            end_date = end_date + timedelta(days=1, seconds=-1)
            query = query.filter(AuditLog.created_at <= end_date)
        except ValueError:
            flash('Invalid end date format', 'error')
    
    # Order by created_at (newest first)
    query = query.order_by(AuditLog.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    
    # For convenience in the template
    filter_params = {
        'action': action,
        'start_date': start_date,
        'end_date': end_date
    }
    
    return render_template(
        'profile/activity_log.html',
        logs=logs,
        pagination=pagination,
        filter_params=filter_params
    )

@profile_bp.route("/export-activity-log")
def export_activity_log():
    """Export activity log as CSV."""
    # Get filter parameters
    action = request.args.get('action')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    query = AuditLog.query.filter_by(user_id=current_user.id)
    
    # Apply filters (same as in activity_log route)
    if action:
        query = query.filter(AuditLog.action == action)
        
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            end_date = end_date + timedelta(days=1, seconds=-1)
            query = query.filter(AuditLog.created_at <= end_date)
        except ValueError:
            pass
    
    # Order by created_at (oldest first for CSV)
    query = query.order_by(AuditLog.created_at)
    
    # Get all results for export
    logs = query.all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Date', 'Time', 'Action', 'Details', 'IP Address'])
    
    # Write data
    for log in logs:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d'),
            log.created_at.strftime('%H:%M:%S'),
            log.action,
            log.details,
            log.ip_address or ''
        ])
    
    # Create response
    output.seek(0)
    date_str = datetime.utcnow().strftime('%Y%m%d')
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"activity_log_{date_str}.csv"
    )

@profile_bp.route("/api-keys")
def api_keys():
    """Manage API keys."""
    # Get user's API keys
    keys = ApiKey.query.filter_by(user_id=current_user.id).all()
    
    return render_template('profile/api_keys.html', api_keys=keys)

@profile_bp.route("/create-api-key", methods=['POST'])
def create_api_key():
    """Create a new API key."""
    key_name = request.form.get('key_name')
    expires_at = request.form.get('expires_at')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not key_name or not confirm_password:
        return jsonify({
            'success': False,
            'message': 'Key name and password are required'
        }), 400
    
    # Verify password
    if not check_password_hash(current_user.password_hash, confirm_password):
        return jsonify({
            'success': False,
            'message': 'Password is incorrect'
        }), 400
    
    # Generate API key
    api_key = secrets.token_urlsafe(32)
    
    # Hash API key
    key_hash = generate_password_hash(api_key)
    
    # Parse expiry date if provided
    expiry = None
    if expires_at:
        try:
            expiry = datetime.strptime(expires_at, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid expiry date format'
            }), 400
    
    # Create API key record
    key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=key_name,
        key_hash=key_hash,
        expires_at=expiry,
        created_at=datetime.utcnow()
    )
    db.session.add(key)
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="api_key_created",
        details=f"API key '{key_name}' created",
        ip_address=request.remote_addr
    )
    db.session.add(audit_log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'API key created successfully',
        'api_key': api_key  # Only returned once upon creation
    })

@profile_bp.route("/revoke-api-key/<key_id>", methods=['POST'])
def revoke_api_key(key_id):
    """Revoke an API key."""
    key = ApiKey.query.filter_by(
        id=key_id,
        user_id=current_user.id
    ).first_or_404()
    
    key.is_active = False
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="api_key_revoked",
        details=f"API key '{key.name}' revoked",
        ip_address=request.remote_addr
    )
    db.session.add(audit_log)
    db.session.commit()
    
    flash('API key has been revoked', 'success')
    return redirect(url_for('profile.api_keys'))
