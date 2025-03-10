import logging
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.user import User, Role
from app.models.user_repository import SqlAlchemyUserRepository
from app.models.audit import AuditLog
from app.decorators.role_required import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix='/admin')
log = logging.getLogger(__name__)
user_repository = SqlAlchemyUserRepository(db)

@admin_bp.before_request
@login_required
@admin_required
def before_request():
    """Ensure all admin routes are protected."""
    pass  # The decorators above handle the protection

@admin_bp.route('/')
def index():
    """Admin dashboard."""
    # Get basic stats for the dashboard
    last_backup_date = None
    # In a real implementation, you would fetch the last backup date
    
    return render_template('admin/index.html', last_backup_date=last_backup_date)

@admin_bp.route('/users')
def users_list():
    """List all users."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'username')
    order = request.args.get('order', 'asc')
    
    # Build query with filters and sorting
    query = db.session.query(User)
    
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) | 
            (User.email.ilike(f'%{search}%'))
        )
    
    # Apply sorting
    if sort == 'email':
        if order == 'asc':
            query = query.order_by(User.email.asc())
        else:
            query = query.order_by(User.email.desc())
    elif sort == 'created_at':
        if order == 'asc':
            query = query.order_by(User.created_at.asc())
        else:
            query = query.order_by(User.created_at.desc())
    elif sort == 'last_login_at':
        if order == 'asc':
            query = query.order_by(User.last_login_at.asc())
        else:
            query = query.order_by(User.last_login_at.desc())
    else:  # Default to username
        if order == 'asc':
            query = query.order_by(User.username.asc())
        else:
            query = query.order_by(User.username.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page)
    users = pagination.items
    total_users = pagination.total
    
    # Calculate total pages
    total_pages = (total_users + per_page - 1) // per_page
    
    return render_template(
        'admin/users.html',
        users=users,
        page=page,
        per_page=per_page,
        total_users=total_users,
        total_pages=total_pages,
        search=search,
        sort=sort,
        order=order
    )

@admin_bp.route('/users/<user_id>')
def user_detail(user_id):
    """View details of a specific user."""
    user = user_repository.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.users_list'))
    
    return render_template('admin/user_detail.html', user=user)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
def user_create():
    """Create a new user."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', Role.USER.value)
        is_active = 'active' in request.form
        
        # Validate inputs
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('admin/user_create.html')
        
        # Check if username or email already exists
        if user_repository.get_by_username(username):
            flash('Username already taken', 'error')
            return render_template('admin/user_create.html')
            
        if user_repository.get_by_email(email.lower()):
            flash('Email already registered', 'error')
            return render_template('admin/user_create.html')
        
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email.lower(),
            password_hash=generate_password_hash(password),
            role=role,
            is_active=is_active,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Set email as verified if user is active
        if is_active:
            user.email_verified_at = datetime.utcnow()
        
        # Save the user
        user_repository.save(user)
        
        # Record audit log
        user_repository.add_audit_log(
            user_id=current_user.id,
            target_user_id=user.id,
            action='user_created',
            details=f"Created user: {username}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash(f'User {username} created successfully', 'success')
        return redirect(url_for('admin.users_list'))
        
    return render_template('admin/user_create.html')

@admin_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
def user_edit(user_id):
    """Edit a user."""
    user = user_repository.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.users_list'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        is_active = 'active' in request.form
        
        # Validate inputs
        if not username or not email or not role:
            flash('All fields are required', 'error')
            return render_template('admin/user_edit.html', user=user)
        
        # Check if username is taken by another user
        if username != user.username:
            existing_user = user_repository.get_by_username(username)
            if existing_user and existing_user.id != user.id:
                flash('Username already taken', 'error')
                return render_template('admin/user_edit.html', user=user)
        
        # Check if email is taken by another user
        if email.lower() != user.email:
            existing_user = user_repository.get_by_email(email.lower())
            if existing_user and existing_user.id != user.id:
                flash('Email already taken', 'error')
                return render_template('admin/user_edit.html', user=user)
        
        # Update user
        changes = []
        if username != user.username:
            old_username = user.username
            user.username = username
            changes.append(f"Username changed from '{old_username}' to '{username}'")
        
        if email.lower() != user.email:
            old_email = user.email
            user.email = email.lower()
            changes.append(f"Email changed from '{old_email}' to '{email}'")
        
        if role != user.role:
            old_role = user.role
            user.role = role
            changes.append(f"Role changed from '{old_role}' to '{role}'")
        
        if is_active != user.is_active:
            user.is_active = is_active
            changes.append(f"Active status changed to: {'Active' if is_active else 'Inactive'}")
            
            # If activating a user, set email as verified
            if is_active and not user.email_verified_at:
                user.email_verified_at = datetime.utcnow()
                changes.append("Email marked as verified")
        
        user.updated_at = datetime.utcnow()
        user_repository.save(user)
        
        # Record audit log
        details = "User updated: " + "; ".join(changes)
        user_repository.add_audit_log(
            user_id=current_user.id,
            target_user_id=user.id,
            action='user_updated',
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash('User updated successfully', 'success')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    
    return render_template('admin/user_edit.html', user=user)

@admin_bp.route('/users/<user_id>/reset-password', methods=['GET', 'POST'])
def user_reset_password(user_id):
    """Reset a user's password."""
    user = user_repository.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.users_list'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password:
            flash('Password is required', 'error')
            return render_template('admin/user_reset_password.html', user=user)
        
        # Update password
        user.password_hash = generate_password_hash(password)
        user.updated_at = datetime.utcnow()
        user_repository.save(user)
        
        # Record audit log
        user_repository.add_audit_log(
            user_id=current_user.id,
            target_user_id=user.id,
            action='password_reset',
            details=f"Password reset for user: {user.username}",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash('Password has been reset successfully', 'success')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    
    return render_template('admin/user_reset_password.html', user=user)

@admin_bp.route('/users/<user_id>/delete', methods=['POST'])
def user_delete(user_id):
    """Delete a user."""
    user = user_repository.get_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin.users_list'))
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    
    username = user.username
    
    # Record audit log before deletion
    user_repository.add_audit_log(
        user_id=current_user.id,
        action='user_deleted',
        details=f"Deleted user: {username} (ID: {user.id})",
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    
    # Delete user
    user_repository.delete(user.id)
    
    flash(f'User {username} has been deleted', 'success')
    return redirect(url_for('admin.users_list'))

@admin_bp.route('/audit-logs')
def audit_logs():
    """View audit logs."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    user_id = request.args.get('user_id', '')
    action = request.args.get('action', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    # Build query with filters
    query = db.session.query(AuditLog)
    
    if user_id:
        query = query.filter(
            (AuditLog.user_id == user_id) | (AuditLog.target_user_id == user_id)
        )
    
    if action:
        query = query.filter(AuditLog.action == action)
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # Add one day to include the entire end date
            end_datetime = end_datetime + timedelta(days=1)
            query = query.filter(AuditLog.created_at < end_datetime)
        except ValueError:
            pass
    
    # Order by most recent first
    query = query.order_by(AuditLog.created_at.desc())
    
    # Paginate results
    logs = query.limit(per_page).offset((page - 1) * per_page).all()
    total_logs = query.count()
    
    # Calculate total pages
    total_pages = (total_logs + per_page - 1) // per_page
    
    # Get list of users for the filter dropdown
    users = db.session.query(User).order_by(User.username).all()
    
    # Get list of distinct actions for the filter dropdown
    actions = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    actions = [a[0] for a in actions]
    
    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        page=page,
        per_page=per_page,
        total_logs=total_logs,
        total_pages=total_pages,
        users=users,
        actions=actions,
        user_id=user_id,
        action=action,
        start_date=start_date,
        end_date=end_date
    )

@admin_bp.route('/system-stats')
def system_stats():
    """View system statistics."""
    stats = {
        'total_users': db.session.query(User).count(),
        'active_users': db.session.query(User).filter_by(is_active=True).count(),
        'admin_users': db.session.query(User).filter_by(role=Role.ADMIN.value).count(),
        'inactive_users': db.session.query(User).filter_by(is_active=False).count(),
        'users_with_2fa': db.session.query(User).filter_by(is_totp_enabled=True).count(),
        'users_with_webauthn': db.session.query(User).filter_by(is_webauthn_enabled=True).count(),
        'locked_accounts': 0,  # Placeholder, implement if you have account locking
        'recent_registrations': db.session.query(User).filter(
            User.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count(),
        'recent_logins': db.session.query(User).filter(
            User.last_login_at >= datetime.utcnow() - timedelta(days=1)
        ).count(),
        'failed_login_attempts': db.session.query(AuditLog).filter(
            AuditLog.action == 'login_failed',
            AuditLog.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
    }
    
    return render_template('admin/system_stats.html', stats=stats)
