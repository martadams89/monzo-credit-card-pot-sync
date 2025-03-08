"""Dependency injection container"""

class ServiceContainer:
    """Simple service container for dependency injection"""
    
    def __init__(self):
        self._services = {}
        
    def register(self, service_name, instance):
        """Register a service instance"""
        self._services[service_name] = instance
        
    def register_factory(self, service_name, factory):
        """Register a factory function that creates the service when needed"""
        def lazy_factory():
            if callable(factory):
                return factory()
            return factory
            
        self._services[service_name] = lazy_factory
        
    def get(self, service_name):
        """Get a service by name"""
        service = self._services.get(service_name)
        
        # If service is a factory, call it to get the actual service
        if callable(service) and not hasattr(service, '__self__'):
            # Not a bound method, so it's probably our factory
            service = service()
            self._services[service_name] = service
            
        return service


# Initialize the container
container = ServiceContainer()

# Setup function to register services
def setup_services(app):
    """Register all services in the container"""
    from app.extensions import db
    from app.models.account_repository import SqlAlchemyAccountRepository
    from app.models.setting_repository import SqlAlchemySettingRepository
    from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository
    from app.models.user_repository import SqlAlchemyUserRepository
    from app.services.cooldown_service import CooldownService
    from app.services.email_service import EmailService
    from app.services.auth_service import AuthService
    from app.services.passkey_service import PasskeyService
    
    # Register repositories
    container.register('db', db)
    container.register('account_repository', SqlAlchemyAccountRepository(db))
    container.register('setting_repository', SqlAlchemySettingRepository(db))
    container.register('history_repository', SqlAlchemySyncHistoryRepository(db))
    container.register('user_repository', SqlAlchemyUserRepository(db))
    
    # Register services
    container.register('cooldown_service', CooldownService(db))
    container.register('email_service', EmailService(container.get('setting_repository')))
    container.register('auth_service', AuthService(container.get('user_repository'), container.get('email_service')))
    container.register('passkey_service', PasskeyService(container.get('user_repository')))
