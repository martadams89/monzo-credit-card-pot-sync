"""Dashboard blueprint routes"""

from flask import render_template, redirect, url_for, flash, current_app, request
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository
from app.services.analytics_service import AnalyticsService
from app.extensions import db

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard page"""
    # ... existing code ...
    
    return render_template('dashboard/index.html', 
                           monzo_account=monzo_account, 
                           credit_accounts=credit_accounts,
                           balances=balances)

@dashboard_bp.route('/refresh')
@login_required
def refresh():
    """Refresh balances"""
    # ... existing code ...
    
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard page"""
    # Get query parameters for filtering
    days = request.args.get('days', 30, type=int)
    account = request.args.get('account', None)
    
    # Get repositories and services
    sync_history_repository = SqlAlchemySyncHistoryRepository(db)
    analytics_service = AnalyticsService(db, sync_history_repository)
    
    # Get analytics data
    stats = analytics_service.get_sync_statistics(days=days)
    trends = analytics_service.get_spending_trends(days=days)
    transactions = analytics_service.get_transaction_history(days=days, account_type=account)
    
    # Prepare data for charts
    monthly_data = trends.get("by_month", {})
    
    return render_template(
        'dashboard/analytics.html', 
        stats=stats, 
        trends=trends, 
        transactions=transactions, 
        monthly_data=monthly_data,
        selected_days=days,
        selected_account=account
    )
