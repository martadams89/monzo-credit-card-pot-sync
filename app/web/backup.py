import os
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash

from app.extensions import db
from app.decorators.role_required import admin_required
from app.utils.backup import create_backup, restore_backup, get_backups, delete_backup, export_data
from app.models.audit import AuditLog

backup_bp = Blueprint("backup", __name__, url_prefix="/backup")

@backup_bp.route("/")
@login_required
@admin_required
def index():
    """Display backup management page."""
    # Get list of available backups
    backups = get_backups()
    
    return render_template('backup/index.html', backups=backups)

@backup_bp.route("/create", methods=['POST'])
@login_required
@admin_required
def create():
    """Create a new database backup."""
    result = create_backup()
    
    if result['success']:
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="backup_created",
            details=f"Created database backup: {result['filename']}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Backup created successfully', 'success')
    else:
        flash(f'Error creating backup: {result["message"]}', 'error')
    
    return redirect(url_for('backup.index'))

@backup_bp.route("/restore/<filename>", methods=['GET'])
@login_required
@admin_required
def restore_confirm(filename):
    """Show confirmation page for restoring a backup."""
    return render_template('backup/restore.html', filename=filename)

@backup_bp.route("/restore/<filename>", methods=['POST'])
@login_required
@admin_required
def restore_backup_endpoint(filename):
    """Restore database from a backup file."""
    password = request.form.get('password')
    
    if not password:
        flash('Please enter your password', 'error')
        return redirect(url_for('backup.restore_confirm', filename=filename))
    
    if not check_password_hash(current_user.password_hash, password):
        flash('Incorrect password', 'error')
        return redirect(url_for('backup.restore_confirm', filename=filename))
    
    result = restore_backup(filename)
    
    if result['success']:
        # Log the action (new session after restore)
        try:
            audit_log = AuditLog(
                user_id=current_user.id,
                action="backup_restored",
                details=f"Restored database from backup: {filename}",
                ip_address=request.remote_addr
            )
            db.session.add(audit_log)
            db.session.commit()
        except:
            # Database might have changed structure, just ignore logging
            pass
        
        flash('Database restored successfully. Please log in again.', 'success')
        return redirect(url_for('auth.logout'))
    else:
        flash(f'Error restoring backup: {result["message"]}', 'error')
        return redirect(url_for('backup.index'))

@backup_bp.route("/delete/<filename>", methods=['POST'])
@login_required
@admin_required
def delete(filename):
    """Delete a backup file."""
    result = delete_backup(filename)
    
    if result['success']:
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="backup_deleted",
            details=f"Deleted database backup: {filename}",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        flash('Backup deleted successfully', 'success')
    else:
        flash(f'Error deleting backup: {result["message"]}', 'error')
    
    return redirect(url_for('backup.index'))

@backup_bp.route("/download/<filename>")
@login_required
@admin_required
def download(filename):
    """Download a backup file."""
    backup_dir = os.path.join(current_app.instance_path, current_app.config['BACKUP_DIRECTORY'])
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        flash('Backup file not found', 'error')
        return redirect(url_for('backup.index'))
    
    # Log the action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="backup_downloaded",
        details=f"Downloaded database backup: {filename}",
        ip_address=request.remote_addr
    )
    db.session.add(audit_log)
    db.session.commit()
    
    return send_file(backup_path, as_attachment=True)

@backup_bp.route("/export")
@login_required
def export():
    """Export user data as JSON."""
    result = export_data(current_user.id)
    
    if result['success']:
        # Generate filename
        filename = f"user_data_export_{current_user.id}.json"
        
        # Create response
        response = jsonify(result['data'])
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        # Log the action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="data_exported",
            details=f"Exported personal data",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return response
    else:
        flash(f'Error exporting data: {result["message"]}', 'error')
        return redirect(url_for('profile.index'))
