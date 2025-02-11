import logging
from sqlalchemy.exc import NoResultFound

from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.errors import AuthException
from app.extensions import db, scheduler
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository

log = logging.getLogger("core")

account_repository = SqlAlchemyAccountRepository(db)
settings_repository = SqlAlchemySettingRepository(db)

def sync_balance():
    with scheduler.app.app_context():
        # Step 1: Retrieve and validate Monzo connection
        try:
            log.info("Retrieving Monzo connection")
            monzo_account: MonzoAccount = account_repository.get_monzo_account()

            log.info("Checking if Monzo access token needs refreshing")
            if monzo_account.is_token_within_expiry_window():
                monzo_account.refresh_access_token()
                account_repository.save(monzo_account)

            log.info("Pinging Monzo connection to verify health")
            monzo_account.ping()
            log.info("Monzo connection is healthy")
        except NoResultFound:
            log.error("No Monzo connection configured; sync will not run")
            monzo_account = None
        except AuthException:
            log.error("Monzo connection authentication failed; deleting configuration and aborting sync")
            account_repository.delete(monzo_account.type)
            monzo_account = None

        log.info("Retrieving credit card connections")
        credit_accounts: list[TrueLayerAccount] = account_repository.get_credit_accounts()
        log.info(f"Retrieved {len(credit_accounts)} credit card connection(s)")

        for credit_account in credit_accounts:
            try:
                log.info(f"Checking if {credit_account.type} access token needs refreshing")
                if credit_account.is_token_within_expiry_window():
                    credit_account.refresh_access_token()
                    account_repository.save(credit_account)

                log.info(f"Pinging {credit_account.type} connection to verify health")
                credit_account.ping()
                log.info(f"{credit_account.type} connection is healthy")
            except AuthException:
                log.error(f"Authentication failed for {credit_account.type}; deleting connection")
                if monzo_account is not None:
                    monzo_account.send_notification(
                        f"{credit_account.type} Pot Sync Access Expired",
                        "Reconnect the account(s) on your portal to resume syncing.",
                    )
                account_repository.delete(credit_account)

        # Exit early if critical connections are missing
        if monzo_account is None or len(credit_accounts) == 0:
            log.info("Missing Monzo connection or credit card connections; skipping sync loop")
            return

        # Check if sync is enabled from settings
        if not settings_repository.get("enable_sync"):
            log.info("Balance sync is disabled in settings; skipping sync loop")
            return

        # Step 2: Calculate balance differentials for each designated credit card pot
        pot_balance_map = {}

        for credit_account in credit_accounts:
            try:
                pot_id = credit_account.pot_id
                if not pot_id:
                    raise NoResultFound(f"No designated credit card pot set for {credit_account.type}")

                # Determine account selection based on account type
                account_selection = monzo_account.get_account_type(pot_id)

                if pot_id not in pot_balance_map:
                    log.info(f"Retrieving balance for credit card pot {pot_id}")
                    pot_balance = monzo_account.get_pot_balance(pot_id)
                    pot_balance_map[pot_id] = {'balance': pot_balance, 'account_selection': account_selection}
                    log.info(f"Credit card pot {pot_id} balance is £{pot_balance / 100:.2f}")
            except NoResultFound as e:
                log.error(str(e))
                return

            log.info(f"Retrieving balance for {credit_account.type} credit card")
            credit_balance = credit_account.get_total_balance()
            log.info(f"{credit_account.type} card balance is £{credit_balance / 100:.2f}")

            # Retrieve pending transactions if applicable (AMEX case)
            pending_amount = 0
            if credit_account.type == "AMEX":
                pending_transactions = credit_account.get_pending_transactions(credit_account.account_id)

                if not isinstance(pending_transactions, list):
                    log.warning(f"Unexpected pending transactions format for {credit_account.type}: {pending_transactions}")
                    pending_transactions = []

                log.info(f"{credit_account.type} Pending Transactions List: {pending_transactions}")  # Log all pending transactions
                
                # Debugging: print each individual transaction
                for txn in pending_transactions:
                    log.info(f"Pending transaction: £{txn / 100:.2f}")  # Log each pending transaction with detailed amounts
                
                pending_amount = sum(txn for txn in pending_transactions if isinstance(txn, (int, float)))

                log.info(f"{credit_account.type} Card - Pending Transactions Total: £{pending_amount / 100:.2f}")

            # Adjusted balance includes pending transactions
            adjusted_balance = credit_balance + pending_amount
            log.info(f"{credit_account.type} Card - Adjusted Balance (including pending): £{adjusted_balance / 100:.2f}")

            # Adjust the designated pot balance based on the adjusted credit card balance
            # If the credit card balance is positive (money owed), subtract it from the pot
            # If the credit card balance is negative (money available), add it to the pot
            if adjusted_balance > 0:
                pot_balance_map[pot_id]['balance'] -= adjusted_balance  # Subtract from the pot
            else:
                pot_balance_map[pot_id]['balance'] += abs(adjusted_balance)  # Add to the pot if it's a credit

        # Step 3: Perform necessary balance adjustments between Monzo account and each pot
        for pot_id, pot_info in pot_balance_map.items():
                pot_diff = pot_info['balance']
                account_selection = pot_info['account_selection']

                try:
                        log.info(f"Retrieving Monzo account balance for {account_selection} account")
                        monzo_balance = monzo_account.get_balance(account_selection=account_selection)
                        log.info(f"Monzo {account_selection} account balance is £{monzo_balance / 100:.2f}")
                except AuthException:
                        log.error(f"Failed to retrieve Monzo {account_selection} account balance; aborting sync loop")
                        return

                log.info(f"Pot {pot_id} balance differential is £{pot_diff / 100:.2f}")

                if pot_diff == 0:
                        log.info("No balance difference; no action required")
                elif pot_diff < 0:
                        # Negative pot_diff means we should deposit into the account
                        difference = abs(pot_diff)
                        if monzo_balance < difference:
                                log.warning(f"Insufficient funds in Monzo account (£{monzo_balance / 100:.2f}); skipping deposit.")
                                monzo_account.send_notification(
                                        "Insufficient Funds for Sync",
                                        "Not enough funds in Monzo account to sync with the credit card pot.",
                                        account_selection=account_selection
                                )
                                continue  # Skip this transaction instead of failing the whole sync process

                        log.info(f"Depositing £{difference / 100:.2f} into Monzo account from pot {pot_id}")
                        monzo_account.add_to_pot(pot_id, difference, account_selection=account_selection)

                else:
                        # Positive pot_diff means we should withdraw from the pot
                        difference = pot_diff
                        try:
                                log.info(f"Withdrawing £{difference / 100:.2f} from Monzo account to pot {pot_id}")
                                monzo_account.withdraw_from_pot(pot_id, difference, account_selection=account_selection)
                        except Exception as e:
                                error_msg = str(e)
                                if "insufficient_funds" in error_msg:
                                        log.warning(f"Not enough funds in pot {pot_id} to withdraw £{difference / 100:.2f}; skipping.")
                                        continue  # Skip withdrawal instead of failing the entire sync
                                else:
                                        log.error(f"Unexpected error while withdrawing from pot {pot_id}: {error_msg}")
                                        raise  # Only crash on unknown errors