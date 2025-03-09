"""Utility for performing system health checks."""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def run_health_check(app, db, service_container):
    """Run health check on all system components.
    
    Args:
        app: Flask application instance
        db: SQLAlchemy database instance
        service_container: Service container instance
        
    Returns:
        dict: Status of each checked component
    """
    health = {}
    
    # Check database connection
    health['database'] = check_database(db)
    
    # Check file system
    health['file_system'] = check_file_permissions(app)
    
    # Check API integrations
    health['monzo_api'] = check_api_integration(service_container, 'monzo_service')
    health['truelayer_api'] = check_api_integration(service_container, 'truelayer_service')
    
    # Check settings repository
    health['settings'] = check_settings_repository(service_container)
    
    # Check scheduler
    health['scheduler'] = check_scheduler(app)
    
    return health

def check_database(db):
    """Check database connection and functionality."""
    try:
        # Get engine
        engine = db.engine
        
        # Execute simple query
        conn = engine.connect()
        result = conn.execute("SELECT 1")
        row = result.fetchone()
        conn.close()
        
        return row[0] == 1
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

def check_file_permissions(app):
    """Check file system permissions."""
    try:
        # Check log directory
        log_dir = app.config.get('LOG_DIR', 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Check if we can write to logs
        test_file = os.path.join(log_dir, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write(f"Test write at {datetime.utcnow()}")
            
        # Clean up
        os.remove(test_file)
        
        return True
    except Exception as e:
        logger.error(f"File permission check failed: {str(e)}")
        return False

def check_api_integration(service_container, service_name):
    """Check API integration service."""
    try:
        service = service_container.get(service_name)
        if not service:
            logger.error(f"Service {service_name} not available")
            return False
            
        # For monzo service
        if service_name == 'monzo_service':
            setting_repo = service_container.get('setting_repository')
            if not setting_repo:
                return False
                
            # Check if api keys are configured
            client_id = setting_repo.get('monzo_client_id')
            client_secret = setting_repo.get('monzo_client_secret')
            
            return bool(client_id and client_secret)
            
        # For truelayer service
        if service_name == 'truelayer_service':
            setting_repo = service_container.get('setting_repository')
            if not setting_repo:
                return False
                
            # Check if api keys are configured
            client_id = setting_repo.get('truelayer_client_id')
            client_secret = setting_repo.get('truelayer_client_secret')
            
            return bool(client_id and client_secret)
            
        return True
    except Exception as e:
        logger.error(f"API integration check failed for {service_name}: {str(e)}")
        return False

def check_settings_repository(service_container):
    """Check settings repository functionality."""
    try:
        setting_repo = service_container.get('setting_repository')
        if not setting_repo:
            return False
            
        # Try a test operation
        test_key = 'health_check_test'
        test_value = f"test_{datetime.utcnow().timestamp()}"
        
        setting_repo.save_setting(test_key, test_value)
        result = setting_repo.get(test_key)
        
        return result == test_value
    except Exception as e:
        logger.error(f"Settings repository check failed: {str(e)}")
        return False

def check_scheduler(app):
    """Check scheduler functionality."""
    try:
        from app.extensions import scheduler
        
        # Check if scheduler is initialized
        if not hasattr(app, 'scheduler') and not scheduler:
            return False
            
        # Check if scheduler is running
        return scheduler.running
    except Exception as e:
        logger.error(f"Scheduler check failed: {str(e)}")
        return False
