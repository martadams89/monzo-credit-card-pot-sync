import logging
import time
import psutil
import platform
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, render_template, current_app
from app.extensions import db, scheduler
from app.models.user_repository import SqlAlchemyUserRepository
from sqlalchemy.sql import text

health_bp = Blueprint('health', __name__)
log = logging.getLogger(__name__)
start_time = datetime.utcnow()

@health_bp.route('/')
def index():
    """Display system health information."""
    try:
        app_status = {
            'version': current_app.config.get('APP_VERSION', '1.0.0'),
            'debug_mode': current_app.debug,
            'db_connection': _check_db_connection()
        }
        
        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'uptime': str(datetime.utcnow() - start_time).split('.')[0]  # Remove microseconds
        }
        
        system_resources = _get_system_resources()
        user_stats = _get_user_stats()
        
        return render_template(
            'health/index.html',
            app_status=app_status,
            system_info=system_info,
            system_resources=system_resources,
            user_stats=user_stats
        )
    except Exception as e:
        return render_template('health/error.html', error=str(e))

@health_bp.route('/api/status')
def api_status():
    """Return system health information as JSON for API consumers."""
    try:
        status = {
            'status': 'healthy' if _check_db_connection() else 'unhealthy',
            'version': current_app.config.get('APP_VERSION', '1.0.0'),
            'timestamp': datetime.utcnow().isoformat(),
            'uptime': str(datetime.utcnow() - start_time).split('.')[0],
            'database': 'connected' if _check_db_connection() else 'disconnected'
        }
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@health_bp.route('/api')
def api():
    """API health check endpoint."""
    start_time = time.time()
    
    health_data = {
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'version': current_app.config.get('VERSION', 'Unknown'),
        'checks': {}
    }
    
    # Check database connection
    try:
        db_start = time.time()
        db_status = _check_db_connection()
        db_duration = time.time() - db_start
        
        health_data['checks']['database'] = {
            'status': 'ok' if db_status else 'error',
            'duration_ms': round(db_duration * 1000, 2)
        }
    except Exception as e:
        health_data['checks']['database'] = {
            'status': 'error',
            'message': str(e)
        }
        health_data['status'] = 'error'
    
    # Add duration information
    health_data['duration_ms'] = round((time.time() - start_time) * 1000, 2)
    
    return jsonify(health_data)

@health_bp.route("/readiness")
def readiness_check():
    """More comprehensive health check to verify system readiness."""
    checks = {
        "database": check_database(),
        "scheduler": check_scheduler()
    }
    
    # Overall status is healthy only if all checks pass
    overall_status = all(c["healthy"] for c in checks.values())
    
    return jsonify({
        "status": "ok" if overall_status else "error",
        "timestamp": time.time(),
        "checks": checks
    }), 200 if overall_status else 503

@health_bp.route("/liveness")
def liveness_check():
    """Simple liveness check to verify the application is responding."""
    return jsonify({
        "status": "ok",
        "timestamp": time.time()
    })

def check_database():
    """Check database connectivity."""
    try:
        # Simple query to test DB connection
        db.session.execute(text("SELECT 1"))
        return {
            "healthy": True,
            "message": "Database connection successful"
        }
    except Exception as e:
        log.error(f"Database health check failed: {str(e)}")
        return {
            "healthy": False,
            "message": str(e)
        }

def check_scheduler():
    """Check if the scheduler is running."""
    try:
        is_running = scheduler.running
        return {
            "healthy": is_running,
            "message": "Scheduler is running" if is_running else "Scheduler is not running"
        }
    except Exception as e:
        log.error(f"Scheduler health check failed: {str(e)}")
        return {
            "healthy": False,
            "message": str(e)
        }

def _check_db_connection():
    """Check if database connection is working."""
    try:
        # Try to execute a simple query
        db.session.execute('SELECT 1')
        return True
    except Exception:
        return False

def _get_system_resources():
    """Get system resource usage."""
    try:
        process = psutil.Process(os.getpid())
        
        # CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)
        
        # Memory usage
        memory_info = process.memory_info()
        memory_usage = f"{memory_info.rss / (1024 * 1024):.1f} MB"
        
        # System memory
        system_memory = psutil.virtual_memory()
        memory_available = f"{system_memory.available / (1024 * 1024 * 1024):.1f} GB"
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage = f"{disk.percent}%"
        disk_free = f"{disk.free / (1024 * 1024 * 1024):.1f} GB"
        
        return {
            'cpu_usage': f"{cpu_percent}%",
            'memory_usage': memory_usage,
            'memory_available': memory_available,
            'disk_usage': disk_usage,
            'disk_free': disk_free
        }
    except Exception as e:
        current_app.logger.error(f"Error getting system resources: {str(e)}")
        return {
            'cpu_usage': 'N/A',
            'memory_usage': 'N/A',
            'memory_available': 'N/A',
            'disk_usage': 'N/A',
            'disk_free': 'N/A'
        }

def _get_user_stats():
    """Get user statistics."""
    try:
        from app.models.user import User
        
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        
        # Get users active in last 24 hours
        day_ago = datetime.utcnow() - timedelta(days=1)
        recently_active = User.query.filter(User.last_login_at >= day_ago).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'recently_active': recently_active
        }
    except Exception as e:
        current_app.logger.error(f"Error getting user stats: {str(e)}")
        return {
            'total_users': 0,
            'active_users': 0,
            'recently_active': 0
        }
