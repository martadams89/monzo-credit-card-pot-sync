"""Service container for dependency injection."""

import logging
from typing import Dict, Any
from flask import current_app, g

logger = logging.getLogger(__name__)

class ServiceContainer:
    """Container for application services."""
    
    def __init__(self):
        """Initialize the service container."""
        self._services: Dict[str, Any] = {}
        self._initialized = False
        
    def initialize(self):
        """Initialize all services."""
        if self._initialized:
            return
            
        logger.info("Service container initialized")
        self._initialized = True
        
        # Core services are initialized on-demand
        
    def register(self, name: str, service: Any) -> None:
        """Register a service in the container.
        
        Args:
            name: Name of the service
            service: The service instance
        """
        self._services[name] = service
        
    def get(self, name: str) -> Any:
        """Get a service from the container by name.
        
        Args:
            name: Name of the service
            
        Returns:
            The service instance, or None if not found
        """
        # Try to find in already initialized services
        if name in self._services:
            return self._services[name]
            
        # Try to initialize lazily
        init_method = getattr(self, f"_init_{name}", None)
        if init_method:
            try:
                service = init_method()
                self._services[name] = service
                return service
            except Exception as e:
                logger.error(f"Error creating service {name}: {str(e)}")
        
        return None
        
    def _init_setting_repository(self):
        """Initialize the setting repository."""
        from app.models.setting_repository import SqlAlchemySettingRepository
        from app.extensions import db
        return SqlAlchemySettingRepository(db)
        
    def _init_user_repository(self):
        """Initialize the user repository."""
        from app.models.user_repository import SqlAlchemyUserRepository
        from app.extensions import db
        return SqlAlchemyUserRepository(db)
        
    def _init_account_repository(self):
        """Initialize the account repository."""
        from app.models.account_repository import SqlAlchemyAccountRepository
        from app.extensions import db
        return SqlAlchemyAccountRepository(db)
        
    def _init_monzo_service(self):
        """Initialize the Monzo service."""
        from app.services.monzo_service import MonzoService
        setting_repository = self.get('setting_repository')
        account_repository = self.get('account_repository')
        return MonzoService(setting_repository, account_repository)
        
    def _init_truelayer_service(self):
        """Initialize the TrueLayer service."""
        from app.services.truelayer_service import TrueLayerService
        setting_repository = self.get('setting_repository')
        account_repository = self.get('account_repository')
        return TrueLayerService(setting_repository, account_repository)
        
    def _init_pot_service(self):
        """Initialize the Pot service."""
        from app.services.pot_service import PotService
        setting_repository = self.get('setting_repository')
        return PotService(setting_repository)
        
    def _init_sync_service(self):
        """Initialize the Sync service."""
        from app.services.sync_service import SyncService
        monzo_service = self.get('monzo_service')
        truelayer_service = self.get('truelayer_service')
        pot_service = self.get('pot_service')
        setting_repository = self.get('setting_repository')
        if not all([monzo_service, truelayer_service, pot_service, setting_repository]):
            return None
        return SyncService(monzo_service, truelayer_service, pot_service, setting_repository)
        
    def _init_auth_service(self):
        """Initialize the Auth service."""
        from app.services.auth_service import AuthService
        user_repository = self.get('user_repository')
        setting_repository = self.get('setting_repository')
        return AuthService(user_repository, setting_repository)
        
    def _init_email_service(self):
        """Initialize the Email service."""
        from app.services.email_service import EmailService
        setting_repository = self.get('setting_repository')
        return EmailService(setting_repository, current_app.config)
        
    def _init_webauthn_service(self):
        """Initialize the WebAuthn service."""
        try:
            from app.services.webauthn_service import WebAuthnService
            from app.models.passkey_repository import SqlAlchemyPasskeyRepository
            from app.extensions import db
            passkey_repository = SqlAlchemyPasskeyRepository(db)
            setting_repository = self.get('setting_repository')
            return WebAuthnService(passkey_repository, setting_repository)
        except ImportError:
            return None
            
    def _init_history_repository(self):
        """Initialize the sync history repository."""
        try:
            from app.models.history_repository import SqlAlchemyHistoryRepository
            from app.extensions import db
            return SqlAlchemyHistoryRepository(db)
        except ImportError:
            return None

    def _init_scheduler_service(self):
        """Initialize the scheduler service."""
        from app.services.scheduler_service import SchedulerService
        setting_repository = self.get('setting_repository')
        sync_service = self.get('sync_service')
        if not setting_repository or not sync_service:
            return None
        return SchedulerService(setting_repository, sync_service)
    
    def _init_email_service(self):
        """Initialize the email service."""
        from app.services.email_service import EmailService
        from flask import current_app
        setting_repository = self.get('setting_repository')
        if not setting_repository or not current_app:
            return None
        return EmailService(setting_repository, current_app.config)

# Create a singleton instance
_container = ServiceContainer()

def container():
    """Get the service container.
    
    Returns:
        ServiceContainer: The service container instance
    """
    if 'service_container' not in g:
        try:
            g.service_container = _container
            if not _container._initialized:
                _container.initialize()
        except Exception as e:
            # Log the error but don't crash
            current_app.logger.error(f"Error initializing service container: {str(e)}")
            # Return a minimal container that can at least function
            if not hasattr(g, 'service_container'):
                g.service_container = ServiceContainer()
    
    return g.service_container
