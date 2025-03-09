"""Admin routes for system management."""

import logging
import os
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.services.container import container
from app.models.user import User
from app.models.account import Account
from app.models.sync_record import SyncRecord
from app.extensions import db
from app.utils.error_handler import handle_error

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Decorator to ensure only admins can access
def admin_required(f):
    """Decorator to ensure only admins can access a route."""
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You need to be an administrator to access this page.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    """Admin index page."""
    # Get system stats
    total_users = User.query.count()
    new_users = User.query.filter(
        User.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    total_accounts = Account.query.count()
    
    syncs_today = SyncRecord.query.filter(
        SyncRecord.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()
    
    # System health check
    health = check_system_health()
    
    stats = {
        'total_users': total_users,
        'new_users': new_users,
        'total_accounts': total_accounts,
        'syncs_today': syncs_today,
        'system_status': 'healthy' if health['status'] == 'ok' else 'issues',
        'last_check': datetime.utcnow()
    }
    
    # Get recent activity
    recent_activity = get_recent_activity()
    
    # Get recent logs
    recent_logs = get_recent_logs()
    
    return render_template('dashboard/admin.html', 
                          title='Admin Dashboard',
                          stats=stats,
                          recent_activity=recent_activity,
                          recent_logs=recent_logs,
                          health=health)

@admin_bp.route('/users')
@admin_required
def users():
    """User management page."""
    users = User.query.all()
    return render_template('admin/users.html', 
                          title='User Management',
                          users=users)

@admin_bp.route('/user/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Create a new user."""
    from app.admin.forms import NewUserForm
    
    form = NewUserForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=form.is_admin.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('User created successfully.', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'error')
    
    return render_template('admin/create_user.html',
                          title='Create User',
                          form=form)

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit a user."""
    from app.admin.forms import UserEditForm
    
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        user.is_active = form.is_active.data
        
        if form.new_password.data:
            user.set_password(form.new_password.data)
            
        db.session.commit()
        flash('User updated successfully.', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/edit_user.html',
                          title='Edit User',
                          form=form,
                          user=user)

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user."""
    if current_user.id == user_id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))
        
    user = User.query.get_or_404(user_id)
    
    try:
        # Delete all user's accounts and data
        Account.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        
        flash('User deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
        
    return redirect(url_for('admin.users'))

@admin_bp.route('/system')
@admin_required
def system():
    """System settings page."""
    setting_repository = container().get('setting_repository')
    settings = setting_repository.get_all()
    
    # Get database stats
    user_count = User.query.count()
    account_count = Account.query.count()
    sync_count = SyncRecord.query.count()
    
    return render_template('admin/system.html',
                          title='System Settings',
                          settings=settings,
                          config=current_app.config,
                          user_count=user_count,
                          account_count=account_count,
                          sync_count=sync_count)

@admin_bp.route('/system/save', methods=['POST'])
@admin_required
def save_system_settings():
    """Save system settings."""
    setting_repository = container().get('setting_repository')
    
    # Process each setting from form data
    for key, value in request.form.items():
        if key.startswith('setting_'):
            setting_key = key[8:]  # Remove 'setting_' prefix
            setting_repository.save_setting(setting_key, value)
    
    flash('System settings updated successfully.', 'success')
    return redirect(url_for('admin.system'))

@admin_bp.route('/maintenance', methods=['POST'])
@admin_required
def run_maintenance():
    """Run system maintenance tasks."""
    try:
        # Clear cache
        if hasattr(current_app, 'cache'):
            current_app.cache.clear()
            
        # Run health check
        health = check_system_health()
        
        # Run database cleanup
        cleanup_database()
        
        # Apply migrations if needed
        from app.utils.migrations_manager import MigrationsManager
        migrations_status = MigrationsManager.apply_migrations()
        
        flash('Maintenance tasks completed successfully.', 'success')
    except Exception as e:
        logger.error(f"Error during maintenance: {str(e)}")
        flash(f'Error during maintenance: {str(e)}', 'error')
        
    return redirect(url_for('admin.index'))

@admin_bp.route('/purge-logs', methods=['POST'])
@admin_required
def purge_logs():
    """Purge application logs."""
    try:
        log_dir = current_app.config.get('LOG_DIR', 'logs')
        
        if os.path.exists(log_dir):
            # Get log files
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            
            # Keep the main log file but truncate it
            main_log = os.path.join(log_dir, 'app.log')
            if os.path.exists(main_log):
                with open(main_log, 'w') as f:
                    f.write(f"Log purged at {datetime.utcnow()}\n")
            
            # Delete rotated log files
            for log_file in log_files:
                if log_file != 'app.log':  # Skip the main log file
                    try:
                        os.remove(os.path.join(log_dir, log_file))
                    except Exception as e:
                        logger.error(f"Error deleting log file {log_file}: {str(e)}")
            
            flash(f'Successfully purged {len(log_files)} log files.', 'success')
        else:
            flash('Log directory not found.', 'warning')
    except Exception as e:
        logger.error(f"Error purging logs: {str(e)}")
        flash(f'Error purging logs: {str(e)}', 'error')
        
    return redirect(url_for('admin.system'))

@admin_bp.route('/logs')
@admin_required
def logs():
    """View system logs."""
    log_file = current_app.config.get('LOG_FILE', os.path.join('logs', 'app.log'))
    
    try:
        with open(log_file, 'r') as f:
            logs = f.read()
    except Exception as e:
        logs = f"Error reading log file: {str(e)}"
    
    return render_template('admin/logs.html',
                          title='System Logs',
                          logs=logs)

@admin_bp.route('/api/accounts')
@admin_required
def api_accounts():
    """API endpoint for account data."""
    accounts = Account.query.all()
    return jsonify([account.to_dict() for account in accounts])

@admin_bp.route('/api/sync-stats')
@admin_required
def api_sync_stats():
    """API endpoint for sync statistics."""
    # Get sync stats from the past 30 days
    start_date = datetime.utcnow() - timedelta(days=30)
    
    # Query for daily stats
    query = db.session.query(
        db.func.date(SyncRecord.timestamp).label('date'),
        db.func.count(SyncRecord.id).label('count'),
        SyncRecord.status
    ).filter(
        SyncRecord.timestamp >= start_date
    ).group_by(
        db.func.date(SyncRecord.timestamp),
        SyncRecord.status
    ).order_by(
        db.func.date(SyncRecord.timestamp)
    )
    
    results = query.all()
    
    # Process into format for charting
    dates = set()
    status_counts = {}
    
    for date, count, status in results:
        date_str = date.strftime('%Y-%m-%d')
        dates.add(date_str)
        
        if status not in status_counts:
            status_counts[status] = {}
        
        status_counts[status][date_str] = count
    
    # Convert to lists for charting
    dates_list = sorted(list(dates))
    
    chart_data = {
        'labels': dates_list,
        'datasets': [
            {
                'label': 'Successful',
                'data': [status_counts.get('success', {}).get(date, 0) for date in dates_list],
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgba(75, 192, 192, 1)',
            },
            {
                'label': 'Failed',
                'data': [status_counts.get('error', {}).get(date, 0) for date in dates_list],
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'borderColor': 'rgba(255, 99, 132, 1)',
            }
        ]
    }
    
    return jsonify(chart_data)

def check_system_health():
    """Check system health."""
    from app.utils.healthcheck import run_health_check
    
    health = run_health_check(current_app, db, container())
    return {
        'status': 'ok' if all(health.values()) else 'error',
        'checks': health
    }

def cleanup_database():
    """Run database cleanup tasks."""
    try:
        # Clean up old sync records
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        deleted = SyncRecord.query.filter(SyncRecord.timestamp < cutoff_date).delete()
        
        # Clean up expired sessions
        # This assumes you're using a database session store
        if hasattr(current_app, 'session_interface') and hasattr(current_app.session_interface, 'cleanup'):
            current_app.session_interface.cleanup()
        
        db.session.commit()
        logger.info(f"Database cleanup complete: {deleted} old sync records deleted")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during database cleanup: {str(e)}")
        raise

def get_recent_activity():
    """Get recent activity for the admin dashboard."""
    # This could be from a dedicated activity log or derived from other tables
    activities = []
    
    # Get recent user registrations
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    for user in recent_users:
        activities.append({
            'user': user.username,
            'action': 'registered an account',
            'timestamp': user.created_at,
            'category': 'Registration',
            'category_class': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
        })
    
    # Get recent syncs
    recent_syncs = SyncRecord.query.order_by(SyncRecord.timestamp.desc()).limit(10).all()
    for sync in recent_syncs:
        user = User.query.get(sync.user_id)
        username = user.username if user else 'Unknown User'
        
        if sync.status == 'success':
            category = 'Success'
            category_class = 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
        elif sync.status == 'error':
            category = 'Error'
            category_class = 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
        else:
            category = sync.status.capitalize()
            category_class = 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300'
            
        activities.append({
            'user': username,
            'action': 'performed a sync',
            'timestamp': sync.timestamp,
            'category': category,
            'category_class': category_class
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Return the most recent 15 activities
    return activities[:15]

def get_recent_logs():
    """Get recent log entries for the admin dashboard."""
    log_file = current_app.config.get('LOG_FILE', os.path.join('logs', 'app.log'))
    
    try:
        # Get the last 50 lines from the log file
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-50:])
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return f"Error reading log file: {str(e)}"
