"""API endpoints for admin functions."""

import logging
import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from app.admin.routes import admin_required
from app.models.user import User
from app.models.account import Account
from app.models.sync_record import SyncRecord
from app.extensions import db

logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/admin/api')

@admin_api_bp.route('/stats')
@admin_required
def get_stats():
    """Get system statistics."""
    try:
        # Basic stats
        stats = {
            'users': {
                'total': User.query.count(),
                'active': User.query.filter_by(is_active=True).count(),
                'inactive': User.query.filter_by(is_active=False).count(),
                'admins': User.query.filter_by(is_admin=True).count(),
                'new_last_7_days': User.query.filter(
                    User.created_at >= datetime.utcnow() - timedelta(days=7)
                ).count()
            },
            'accounts': {
                'total': Account.query.count(),
                'monzo': Account.query.filter_by(type='monzo').count(),
                'credit_card': Account.query.filter_by(type='credit_card').count()
            },
            'syncs': {
                'total': SyncRecord.query.count(),
                'successful': SyncRecord.query.filter_by(status='success').count(),
                'failed': SyncRecord.query.filter_by(status='error').count(),
                'last_24_hours': SyncRecord.query.filter(
                    SyncRecord.timestamp >= datetime.utcnow() - timedelta(days=1)
                ).count()
            },
            'server': {
                'uptime': get_server_uptime(),
                'python_version': get_python_version(),
                'flask_version': get_flask_version()
            }
        }
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_api_bp.route('/recent-activity')
@admin_required
def get_recent_activity():
    """Get recent system activity."""
    try:
        # Get activity data
        activity = []
        
        # Get recent user registrations
        recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
        for user in recent_users:
            activity.append({
                'type': 'user_registration',
                'user': user.username,
                'email': user.email,
                'timestamp': user.created_at.isoformat() if user.created_at else None,
                'data': {
                    'id': user.id,
                    'is_admin': user.is_admin,
                    'is_active': user.is_active
                }
            })
        
        # Get recent syncs
        recent_syncs = SyncRecord.query.order_by(SyncRecord.timestamp.desc()).limit(20).all()
        for sync in recent_syncs:
            user = User.query.get(sync.user_id)
            username = user.username if user else f"User #{sync.user_id}"
            
            activity.append({
                'type': 'sync',
                'user': username,
                'status': sync.status,
                'timestamp': sync.timestamp.isoformat() if sync.timestamp else None,
                'data': {
                    'id': sync.id,
                    'details': json.loads(sync.details) if sync.details else {}
                }
            })
        
        # Sort by timestamp
        activity.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify(activity[:20])  # Return top 20
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_api_bp.route('/health')
@admin_required
def get_health():
    """Get system health status."""
    from app.utils.healthcheck import run_health_check
    from app.services.container import container
    
    try:
        health = run_health_check(current_app, db, container())
        return jsonify({
            'status': 'ok' if all(health.values()) else 'error',
            'checks': health,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

def get_server_uptime():
    """Get server uptime."""
    try:
        import subprocess
        uptime = subprocess.check_output(['uptime']).decode('utf-8').strip()
        return uptime
    except:
        return "Unknown"

def get_python_version():
    """Get Python version."""
    import sys
    return sys.version

def get_flask_version():
    """Get Flask version."""
    import flask
    return flask.__version__
