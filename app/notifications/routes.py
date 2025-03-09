"""Routes for the notifications system."""

from flask import jsonify, request
from flask_login import current_user, login_required
from app.notifications import notifications_bp
from app.models.notification_repository import SqlAlchemyNotificationRepository
from app.extensions import db

notification_repository = SqlAlchemyNotificationRepository(db)

@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get current user's notifications."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 50)
    
    notifications = notification_repository.get_user_notifications(
        user_id=current_user.id,
        page=page,
        per_page=per_page
    )
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications.items],
        'pagination': {
            'page': notifications.page,
            'pages': notifications.pages,
            'total': notifications.total
        }
    })

@notifications_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notification_read():
    """Mark notification as read."""
    data = request.get_json()
    
    if not data or 'notification_id' not in data:
        return jsonify({'error': 'Missing notification ID'}), 400
        
    success = notification_repository.mark_as_read(
        notification_id=data['notification_id'],
        user_id=current_user.id
    )
    
    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Failed to mark notification as read'}), 404
