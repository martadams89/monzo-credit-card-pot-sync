"""Main blueprint routes"""

import logging
from flask import render_template, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.main import main_bp
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository
from app.extensions import db
from app.services.container import container
import datetime
import json

log = logging.getLogger("main_routes")

@main_bp.route('/status')
@login_required
def status():
    """Display system status"""
    # Get repositories and services from container
    history_repository = container().get('history_repository')
    sync_service = container().get('sync_service')
    account_service = container().get('account_service')
    setting_repository = container().get('setting_repository')
    
    # Fetch sync history (most recent entries)
    sync_history = history_repository.get_sync_history(
        datetime.datetime.now() - datetime.timedelta(days=2), 
        datetime.datetime.now(),
        limit=20
    )
    
    # Get system stats
    stats = {
        "total_syncs": history_repository.count_syncs(),
        "successful_syncs": history_repository.count_syncs(status="completed"),
        "failed_syncs": history_repository.count_syncs(status="error"),
        "last_sync": history_repository.get_latest_sync()
    }
    
    # Determine overall system status
    system_status = {
        "monzo_api": "operational",
        "truelayer_api": "operational",
        "database": "operational",
        "scheduler": "operational"
    }
    
    # Check if sync is enabled
    system_status["sync_enabled"] = setting_repository.get("enable_sync") == "True"
    
    # Check if we've had any recent failures
    recent_errors = history_repository.count_syncs(
        status="error",
        start_date=datetime.datetime.now() - datetime.timedelta(hours=3)
    )
    
    if recent_errors > 0:
        system_status["recent_errors"] = recent_errors
        
    # Get account information
    try:
        accounts = account_service.get_all_accounts()
        system_status["accounts"] = len(accounts)
        
        # Check token validity for APIs
        for account in accounts:
            if account.provider == "monzo" and account.token_expires_at < datetime.datetime.now():
                system_status["monzo_api"] = "token_expired"
            elif account.provider == "truelayer" and account.token_expires_at < datetime.datetime.now():
                system_status["truelayer_api"] = "token_expired"
    except Exception as e:
        log.error(f"Error checking accounts: {e}")
        system_status["accounts"] = "error"
    
    return render_template('main/status.html', 
                           sync_history=sync_history, 
                           stats=stats, 
                           system_status=system_status)

@main_bp.route('/health')
def health():
    """Health check endpoint - accessible without login
    Used by Docker, Kubernetes, and monitoring systems
    Returns:
        JSON: Health status with details
    """
    health_status = {
        "status": "ok",
        "components": {
            "api": {"status": "ok"},
            "database": {"status": "ok"},
            "version": current_app.config.get("VERSION", "unknown")
        },
        "checks": []
    }
    
    # Check database connection
    try:
        db.session.execute("SELECT 1")
        health_status["checks"].append({
            "name": "database_connection",
            "status": "pass"
        })
    except SQLAlchemyError as e:
        log.error(f"Database connection error: {e}")
        health_status["status"] = "error"
        health_status["components"]["database"]["status"] = "error"
        health_status["checks"].append({
            "name": "database_connection",
            "status": "fail",
            "message": "Database connection failed"
        })
    
    # Status code based on overall health
    status_code = 200 if health_status["status"] == "ok" else 503
    
    return jsonify(health_status), status_code

@main_bp.route('/readiness')
def readiness():
    """Readiness probe for Kubernetes"""
    return jsonify({"status": "ready"}), 200

@main_bp.route('/liveness')
def liveness():
    """Liveness probe for Kubernetes"""
    return jsonify({"status": "alive"}), 200
