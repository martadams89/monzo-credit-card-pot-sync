"""Utility to verify service container initialization."""

import logging
import sys
from flask import Flask
from app.services.container import container

log = logging.getLogger(__name__)

def verify_services():
    """Verify that all services can be initialized properly."""
    try:
        # Create a minimal Flask app context
        app = Flask(__name__)
        with app.app_context():
            # Get container
            service_container = container()
            
            # Try to get all critical services
            services = [
                'user_repository',
                'setting_repository',
                'account_repository',
                'cooldown_repository',
                'history_repository',
                'email_service',
                'backup_service',
                'auth_service',
                'passkey_service',
                'account_service',
                'cooldown_service',
                'metrics_service',
                'cooldown_processor',
                'account_processor',
                'sync_service'
            ]
            
            errors = []
            for service_name in services:
                try:
                    service = service_container.get(service_name)
                    if service is None:
                        errors.append(f"Service '{service_name}' returned None")
                except Exception as e:
                    errors.append(f"Error initializing '{service_name}': {str(e)}")
            
            if errors:
                log.error("Service container verification failed:")
                for error in errors:
                    log.error(f"  - {error}")
                return False
            else:
                log.info("All services initialized successfully")
                return True
    except Exception as e:
        log.error(f"Error during service verification: {str(e)}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the verification
    result = verify_services()
    sys.exit(0 if result else 1)
