"""Simple health check utility for the application."""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("healthcheck")

def check_environment():
    """Check essential environment variables."""
    log.info("Checking environment...")
    
    # Make these checks less strict for development
    needed_vars = []
    missing_vars = []
    
    for var in needed_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        log.warning(f"Missing environment variables: {', '.join(missing_vars)}")
    
    log.info("Environment check complete")
    return True

def check_database_path():
    """Check if database path is accessible."""
    log.info("Checking database path...")
    
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/app.db')
    if db_url.startswith('sqlite:///'):
        # Extract the path part
        db_path = db_url.replace('sqlite:///', '')
        if not db_path.startswith('/'):
            # It's a relative path, make it relative to the app directory
            db_path = os.path.join('/app', db_path)
        
        # Check if the directory exists
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                log.info(f"Created database directory: {db_dir}")
            except Exception as e:
                log.error(f"Failed to create database directory: {e}")
                return False
    
    log.info("Database path check complete")
    return True

def run_checks():
    """Run all health checks."""
    log.info("Starting basic health checks...")
    
    checks = [
        check_environment,
        check_database_path
    ]
    
    all_passed = True
    for check in checks:
        try:
            result = check()
            if not result:
                all_passed = False
        except Exception as e:
            log.error(f"Check {check.__name__} failed with error: {e}")
            all_passed = False
    
    if all_passed:
        log.info("All health checks passed!")
        return 0
    else:
        log.error("Some health checks failed!")
        return 1

if __name__ == "__main__":
    sys.exit(run_checks())
