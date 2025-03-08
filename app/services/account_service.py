"""Service for handling account operations and validation"""

import logging
from sqlalchemy.exc import NoResultFound
from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.errors import AuthException
from app.utils.api_helpers import retry_on_exception

log = logging.getLogger("account_service")

class AccountService:
    """Service for managing account operations"""
    
    def __init__(self, account_repository, settings_repository=None):
        self.account_repository = account_repository
        self.settings_repository = settings_repository
    
    def initialize_monzo_account(self):
        """
        Initialize and validate Monzo account - SECTION 1
        Returns authenticated Monzo account or None if unavailable
        """
        try:
            log.info("Retrieving Monzo connection")
            monzo_account = self.account_repository.get_monzo_account()
            
            log.info("Checking if Monzo access token needs refreshing")
            if monzo_account.is_token_within_expiry_window():
                monzo_account.refresh_access_token()
                self.account_repository.save(monzo_account)
                
            log.info("Pinging Monzo connection to verify health")
            monzo_account.ping()
            log.info("Monzo connection is healthy")
            
            return monzo_account
        except Exception as e:
            log.error(f"Error initializing Monzo account: {e}")
            return None
    
    @retry_on_exception(max_retries=3, allowed_exceptions=(IOError, ConnectionError))
    def get_credit_accounts(self, monzo_account=None):
        """
        Retrieve and validate credit accounts - SECTION 2
        Returns list of valid credit accounts
        """
        log.info("Retrieving credit card connections")
        credit_accounts = self.account_repository.get_credit_accounts()
        log.info(f"Retrieved {len(credit_accounts)} credit card connection(s)")
        
        valid_accounts = []
        for credit_account in credit_accounts:
            try:
                log.info(f"Checking if {credit_account.type} access token needs refreshing")
                if credit_account.is_token_within_expiry_window():
                    credit_account.refresh_access_token()
                    self.account_repository.save(credit_account)
                
                log.info(f"Checking health of {credit_account.type} connection")
                credit_account.ping()
                log.info(f"{credit_account.type} connection is healthy")
                
                valid_accounts.append(credit_account)
            except AuthException as e:
                log.error(f"Authentication error for {credit_account.type}: {e}")
                if monzo_account:
                    self._handle_auth_error(monzo_account, credit_account, e)
                
        return valid_accounts
    
    def _handle_auth_error(self, monzo_account, credit_account, error):
        """Handle authentication errors for credit accounts"""
        details = getattr(error, 'details', {})
        description = details.get('error_description', '')
        
        if "currently unavailable" in description or details.get('error') == 'provider_error':
            log.info(f"Service provider for {credit_account.type} is currently unavailable, will retry later.")
        else:
            if monzo_account is not None:
                monzo_account.send_notification(
                    f"{credit_account.type} Pot Sync Access Expired",
                    "Your connection to this credit card provider has expired. Please reconnect it in the Monzo Credit Card Pot Sync portal.",
                )
            self.account_repository.delete(credit_account.type)
