import datetime  # Needed for human-readable time conversions
import logging
from time import time
from urllib import parse

import requests as r

from app.errors import AuthException, PotNotFoundError, PotTransferError

log = logging.getLogger("account")


class Account:
    def __init__(
        self,
        type,
        access_token=None,
        refresh_token=None,
        token_expiry=None,
        pot_id=None,
        account_id=None,
        cooldown_until=None,
        prev_balance=0,
        cooldown_ref_card_balance=None,
        cooldown_ref_pot_balance=None,
        stable_pot_balance=None,
        provider_type=None,
        include_pending_credits=True,
    ):
        self.type = type
        self.provider_type = provider_type or type
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = token_expiry
        self.pot_id = pot_id
        self.account_id = account_id
        self.cooldown_until = cooldown_until
        self.prev_balance = prev_balance
        self.cooldown_ref_card_balance = cooldown_ref_card_balance
        self.cooldown_ref_pot_balance = cooldown_ref_pot_balance
        self.stable_pot_balance = stable_pot_balance
        self.include_pending_credits = include_pending_credits


    def is_token_within_expiry_window(self):
        # Returns True if the token expires in the next two minutes or has already expired.
        return self.token_expiry - int(time()) <= 120

    def refresh_access_token(self):
        log.info(f"{self.type} access token is within expiry window, refreshing tokens")
        try:
            tokens = self.auth_provider.refresh_access_token(self.refresh_token)
            sanitized_tokens = {k: "***REDACTED***" if "token" in k else v for k, v in tokens.items()}
            log.debug(f"{self.type} token refresh response: {sanitized_tokens}")
    
            if "access_token" not in tokens or "refresh_token" not in tokens:
                log.error(f"{self.type} token refresh response missing fields: {sanitized_tokens}")
                exc = AuthException("Access token refresh response missing required fields")
                exc.details = tokens  # attach provider response details
                raise exc
    
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
            self.token_expiry = int(time()) + tokens["expires_in"]
            token_expiry_hr = datetime.datetime.fromtimestamp(
                self.token_expiry, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")
            log.info(f"Successfully refreshed {self.type} access token, new expiry time is {token_expiry_hr}")
    
        except KeyError as e:
            log.error(f"KeyError while refreshing {self.type} token: {e!s} - Response: {sanitized_tokens}")
            raise AuthException("Unexpected token response format") from e
    
        except AuthException:
            log.error(f"Failed to refresh access token for {self.type}")
            raise

    def get_auth_header(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def pre_deposit_check(self, current_balance, new_balance, cooldown_duration):
        """
        Only activate cooldown when the new pot balance is lower than the previous balance.
        """
        now = int(time())
        if new_balance < current_balance:
            if self.cooldown_until and now < self.cooldown_until:
                log.info(f"Cooldown active until {self.cooldown_until}. Deposit postponed for {self.type}.")
                return False
            else:
                self.cooldown_until = now + cooldown_duration
                log.info(f"Pot balance decreased. Initiating cooldown until {self.cooldown_until} for {self.type}.")
                return False
        return True

    def get_prev_balance(self, pot_id: str) -> int:
        # Retrieve the persisted previous balance; fallback to 0 if not stored.
        try:
            return int(self.prev_balance) if self.prev_balance is not None else 0
        except (TypeError, ValueError):
            return 0

class MonzoAccount(Account):
    def __init__(self, access_token, refresh_token, token_expiry, pot_id="default_pot", account_id=None, prev_balance=0):
        super().__init__(
            type="Monzo",
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            pot_id=pot_id,
            account_id=account_id,
            prev_balance=prev_balance
        )
        # Initialize the auth provider for Monzo
        from app.domain.auth_providers import MonzoAuthProvider
        self.auth_provider = MonzoAuthProvider()

    def ping(self) -> None:
        r.get(
            f"{self.auth_provider.api_url}/ping/whoami", headers=self.get_auth_header()
        )

    def _fetch_accounts(self) -> list:
        response = r.get(
            f"{self.auth_provider.api_url}/accounts", headers=self.get_auth_header()
        )
        response.raise_for_status()
        accounts = response.json()["accounts"]
        # Filter out closed accounts
        open_accounts = [account for account in accounts if not account.get("closed", False)]
        return open_accounts

    def get_authorized_accounts(self) -> list:
        """Return a list of authorized accounts (both personal and joint) with details."""
        return self._fetch_accounts()

    def get_account_id(self, account_selection="personal") -> str:
        # Normalize account selection to one of: personal, joint, business
        if account_selection not in ("personal", "joint", "business"):
            account_selection = "personal"
        
        # Map account selection to Monzo API account type
        type_mapping = {
            "personal": "uk_retail",
            "joint": "uk_retail_joint",
            "business": "uk_business"
        }
        desired_type = type_mapping[account_selection]
        
        accounts = self._fetch_accounts()
        for account in accounts:
            if account["type"] == desired_type:
                return account["id"]
        raise AuthException(f"No account found for type: {desired_type}")

    def get_account_description(self, account_selection="personal") -> str:
        """Return the account description for the selected account."""
        desired_id = self.get_account_id(account_selection=account_selection)
        accounts = self._fetch_accounts()
        for account in accounts:
            if account["id"] == desired_id:
                return account.get("description", "")
        return ""

    def get_balance(self, account_selection="personal") -> int:
        """
        Retrieve the balance for the specified account type.
        :param account_selection: 'personal' for personal account, 'joint' for joint account, 'business' for business account.
        :return: Balance in minor units (e.g., pence for GBP).
        """
        account_id = self.get_account_id(account_selection=account_selection)
        query = parse.urlencode({"account_id": account_id})
        response = r.get(
            f"{self.auth_provider.api_url}/balance?{query}",
            headers=self.get_auth_header(),
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()["balance"]

    def get_pots(self, account_selection="personal") -> list:
        """
        Get pots based on the selected account type.
        By default, uses the personal account; for joint, pass account_selection="joint"; for business, pass account_selection="business".
        """
        current_account_id = self.get_account_id(account_selection)
        query = parse.urlencode({"current_account_id": current_account_id})
        response = r.get(
            f"{self.auth_provider.api_url}/pots?{query}", headers=self.get_auth_header()
        )
        response.raise_for_status()
        pots = response.json()["pots"]
        return [p for p in pots if not p["deleted"]]

    def get_pot_balance(self, pot_id: str) -> int:
        # Try personal account first, then joint, then business account if needed.
        for account_selection in ("personal", "joint", "business"):
            pots = self.get_pots(account_selection)
            pot = next((p for p in pots if p["id"] == pot_id), None)
            if pot is not None:
                return pot["balance"]
        raise PotNotFoundError(f"Pot with id {pot_id} not found in personal, joint, or business pots.")

    def get_account_type(self, pot_id: str) -> str:
        """
        Retrieve the account type (personal, joint, or business) for the given pot ID.
        """
        for account_selection in ("personal", "joint", "business"):
            pots = self.get_pots(account_selection)
            # If using the default value, fall back to the first returned pot's id.
            if pot_id == "default_pot" and pots:
                pot_id = pots[0]["id"]
            if any(p["id"] == pot_id for p in pots):
                return account_selection
        raise PotNotFoundError(f"Pot with id {pot_id} not found in personal, joint, or business pots.")

    def add_to_pot(self, pot_id: str, amount: int, account_selection="personal") -> None:
        # Normalize account_selection immediately
        if account_selection not in ("personal", "joint", "business"):
            account_selection = "personal"
        
        # Retrieve pot details using normalized account_selection
        pots = self.get_pots(account_selection)
        pot = next((p for p in pots if p["id"] == pot_id), None)
        if not pot:
            raise PotNotFoundError(f"Pot with id {pot_id} not found in {account_selection} pots")
            
        # Re-fetch pot list for extra safety
        pots = self.get_pots(account_selection=account_selection)
        pot = next((p for p in pots if p["id"] == pot_id), None)
        if pot is None:
            raise PotNotFoundError(f"Pot with id {pot_id} not found in {account_selection} pots")
    
        data = {
            "source_account_id": self.get_account_id(account_selection=account_selection),
            "amount": amount,
            "dedupe_id": str(int(time())),  # Ensure dedupe_id is a string
        }
        response = r.put(
            f"{self.auth_provider.api_url}/pots/{pot_id}/deposit",
            data=data,
            headers=self.get_auth_header(),
        )
        if response.status_code != 200:
            log.error(f"Failed to deposit to pot: {response.json()}")
            raise PotTransferError(f"Deposit failed: {response.json()}")

    def withdraw_from_pot(self, pot_id: str, amount: int, account_selection="personal") -> None:
        # Normalize account_selection immediately
        if account_selection not in ("personal", "joint", "business"):
            account_selection = "personal"
        
        # Retrieve pot details using normalized account_selection
        pots = self.get_pots(account_selection)
        pot = next((p for p in pots if p["id"] == pot_id), None)
        if not pot:
            raise PotNotFoundError(f"Pot with id {pot_id} not found in {account_selection} pots")
        
        # Re-fetch pot list for extra safety
        pots = self.get_pots(account_selection=account_selection)
        pot = next((p for p in pots if p["id"] == pot_id), None)
        if pot is None:
            raise PotNotFoundError(f"Pot with id {pot_id} not found in {account_selection} pots")
    
        data = {
            "destination_account_id": self.get_account_id(account_selection=account_selection),
            "amount": amount,
            "dedupe_id": str(int(time())),  # Ensure dedupe_id is a string
        }
        response = r.put(
            f"{self.auth_provider.api_url}/pots/{pot_id}/withdraw",
            data=data,
            headers=self.get_auth_header(),
        )
        if response.status_code != 200:
            log.error(f"Failed to withdraw from pot: {response.json()}")
            raise PotTransferError(f"Withdrawal failed: {response.json()}")

    def send_notification(self, title: str, message: str, account_selection="personal") -> None:
        body = {
            "account_id": self.get_account_id(account_selection=account_selection),
            "type": "basic",
            "params[image_url]": "https://www.nyan.cat/cats/original.gif",
            "params[title]": title,
            "params[body]": message,
        }
        r.post(
            f"{self.auth_provider.api_url}/feed",
            data=body,
            headers=self.get_auth_header(),
        )


class TrueLayerAccount(Account):
    # Providers whose pending refunds and payments are added to the balance; each
    # connection can switch this off (``include_pending_credits``) if the provider
    # turns out to take a pending payment off the current balance as well, which
    # would count it twice.
    PENDING_CREDIT_PROVIDERS = ("American Express", "Lloyds")

    def __init__(
        self,
        account_type,
        access_token=None,
        refresh_token=None,
        token_expiry=None,
        pot_id=None,
        account_id=None,
        prev_balance=0,
        stable_pot_balance=None,
        cooldown_ref_card_balance=None,
        cooldown_ref_pot_balance=None,
        cooldown_until=None,
        provider_type=None,
        include_pending_credits=True,
    ):
        super().__init__(
            account_type,
            access_token,
            refresh_token,
            token_expiry,
            pot_id,
            account_id,
            cooldown_until=cooldown_until,  # Pass it to the parent initializer
            prev_balance=prev_balance,
            stable_pot_balance=stable_pot_balance,
            cooldown_ref_card_balance=cooldown_ref_card_balance,
            cooldown_ref_pot_balance=cooldown_ref_pot_balance,
            provider_type=provider_type,
            include_pending_credits=include_pending_credits,
        )
        from app.domain.auth_providers import TrueLayerAuthProvider

        provider_name = self.provider_type.lower()
        if provider_name == "american express":
            icon = "amex.svg"
        elif provider_name == "barclaycard":
            icon = "barclaycard.svg"
        elif provider_name == "halifax":
            icon = "halifax.svg"
        elif provider_name == "lloyds":
            icon = "lloyds.svg"
        elif provider_name == "natwest":
            icon = "natwest.svg"
        else:
            icon = "truelayer.svg"
        self.auth_provider = TrueLayerAuthProvider(
            name="TrueLayer",
            type="truelayer",
            icon_name=icon
        )

    def ping(self) -> None:
        r.get(f"{self.auth_provider.api_url}/data/v1/me", headers=self.get_auth_header())

    def get_cards(self) -> list:
        response = r.get(f"{self.auth_provider.api_url}/data/v1/cards", headers=self.get_auth_header())
        response.raise_for_status()
        return response.json()["results"]

    def get_card_balance(self, card_id: str) -> float:
        response = r.get(f"{self.auth_provider.api_url}/data/v1/cards/{card_id}/balance", headers=self.get_auth_header())
        response.raise_for_status()
        data = response.json()["results"][0]
        # Round to whole pence; ceil() would turn float noise (2.2 * 100 == 220.00000000000003) into an extra penny
        return round(data["current"] * 100) / 100

    def get_pending_transactions(self, card_id: str) -> list:
        response = r.get(f"{self.auth_provider.api_url}/data/v1/cards/{card_id}/transactions/pending", headers=self.get_auth_header())
        response.raise_for_status()
        transactions = response.json()["results"]
        return [self._signed_pending_amount(txn) for txn in transactions] if transactions else []

    @staticmethod
    def _signed_pending_amount(txn: dict) -> float:
        """Return a pending amount as charge-positive, credit-negative, in whole pence.

        Charges add to what is owed and must be positive; refunds and payments
        reduce it and must be negative. The sign normally comes from the amount
        itself, but where the provider labels the transaction DEBIT or CREDIT
        that label wins, so a credit reported with a positive amount is not
        counted as a charge (and vice versa).
        """
        # round() rather than ceil(): ceil turns float noise such as 1.1 * 100 ==
        # 110.00000000000001 into an extra penny, and rounds charges and credits
        # in opposite directions.
        pence = round(float(txn["amount"]) * 100)
        transaction_type = str(txn.get("transaction_type") or "").upper()
        if transaction_type == "CREDIT":
            pence = -abs(pence)
        elif transaction_type == "DEBIT":
            pence = abs(pence)
        return pence / 100

    @property
    def supports_pending_credits(self) -> bool:
        """Whether this connection's provider adds pending refunds and payments."""
        return self.provider_type in self.PENDING_CREDIT_PROVIDERS

    def _balance_with_pending(self, label: str, balance: float, pending_transactions: list) -> float:
        """Add pending charges and pending credits (refunds, payments) to a card balance.

        Providers such as Amex and Lloyds report pending charges and pending credits
        as separate transactions rather than netting them off, so both are counted;
        otherwise a pending refund leaves the pot over-funded until it posts. Works
        in whole pence so charges and credits of either sign add up exactly.
        """
        balance_pence = round(balance * 100)
        pending_pence = [round(txn * 100) for txn in pending_transactions]

        # Separate charges (positive) and payments/refunds (negative)
        pending_charges_pence = sum(p for p in pending_pence if p > 0)
        pending_payments_pence = sum(p for p in pending_pence if p < 0)
        if self.include_pending_credits:
            pending_balance_pence = pending_charges_pence + pending_payments_pence
        else:
            pending_balance_pence = pending_charges_pence
            log.info(f"{label} - Pending payments/refunds not counted (switched off for {self.type})")
        adjusted_balance_pence = balance_pence + pending_balance_pence

        log.info(f"{label} - Current Balance (Excluding Pending Transactions): £{balance_pence / 100:.2f}")
        log.info(f"{label} - Pending Charges: £{pending_charges_pence / 100:.2f}")
        log.info(f"{label} - Pending Payments/Refunds: £{pending_payments_pence / 100:.2f}")
        log.info(f"{label} - Pending Balance: £{pending_balance_pence / 100:.2f}")
        log.info(f"{label} - Total Balance: £{adjusted_balance_pence / 100:.2f}")
        return adjusted_balance_pence / 100

    def get_total_balance(self, force_refresh=False) -> int:
        # If we have a cached balance and not forcing a refresh, return it without
        # calling the API.
        if not force_refresh and hasattr(self, "_cached_balance"):
            return self._cached_balance

        total_balance = 0.0
        cards = self.get_cards()

        for card in cards:
            card_id = card["account_id"]
            provider = card.get("provider", {}).get("display_name")

            # Fetch balance data once for all providers
            balance_response = r.get(f"{self.auth_provider.api_url}/data/v1/cards/{card_id}/balance", headers=self.get_auth_header())
            balance_response.raise_for_status()
            balance_data = balance_response.json()["results"][0]
            
            # For most providers, use the 'current' field
            balance = round(balance_data.get("current", 0) * 100) / 100

            if provider in ["AMEX"]:
                balance = self._balance_with_pending("Amex Card", balance, self.get_pending_transactions(card_id))

            if provider in ["BARCLAYCARD"]:
                pending_transactions = self.get_pending_transactions(card_id)

                # Separate charges and payments/refunds
                pending_charges = round(sum(txn for txn in pending_transactions if txn > 0) * 100) / 100
                pending_payments = round(sum(txn for txn in pending_transactions if txn < 0) * 100) / 100
                net_pending = round(sum(pending_transactions) * 100) / 100

                log.info(f"Barclaycard Card - Current Balance: £{balance:.2f}")
                log.info(f"Barclaycard Card - Pending Charges: £{pending_charges:.2f}")
                log.info(f"Barclaycard Card - Pending Payments: £{pending_payments:.2f}")
                log.info(f"Barclaycard Card - Net Pending: £{net_pending:.2f}")

                # Barclaycard adds pending charges to the current balance fairly quickly,
                # so pending transactions are logged only and the balance is used as is.

            if provider in ["HALIFAX"]:
                # Halifax doesn't provide separate pending transactions
                # The 'available' field already accounts for pending charges
                # Balance owed = credit_limit - available
                credit_limit = balance_data.get("credit_limit", 0)
                available = balance_data.get("available", 0)
                balance_owed = credit_limit - available
                
                log.info(f"Halifax Card - Credit Limit: £{credit_limit:.2f}")
                log.info(f"Halifax Card - Available Credit: £{available:.2f}")
                log.info(f"Halifax Card - Balance Owed: £{balance_owed:.2f}")
                
                balance = round(balance_owed * 100) / 100

            if provider in ["LLOYDS"]:
                balance = self._balance_with_pending("Lloyds Card", balance, self.get_pending_transactions(card_id))

            # A card in credit (overpaid, or pending credits exceeding what is owed)
            # owes nothing. A negative figure would otherwise eat into the amounts owed
            # on the other cards in this total.
            if balance < 0:
                log.info(f"Card is in credit (£{balance:.2f}); treating as £0.00 owed.")
                balance = 0.0

            total_balance += balance

        log.info(f"Total balance calculated: £{total_balance:.2f}")
        # round() rather than int(): int() truncates float noise such as 0.29 * 100
        # == 28.999999999999996 down a penny.
        self._cached_balance = round(total_balance * 100)  # Convert balance to pence
        return self._cached_balance

        for card in cards:
            card_id = card["account_id"]
            provider = card.get("provider", {}).get("display_name")

            # Fetch balance data once for all providers
            balance_response = r.get(f"{self.auth_provider.api_url}/data/v1/cards/{card_id}/balance", headers=self.get_auth_header())
            balance_response.raise_for_status()
            balance_data = balance_response.json()["results"][0]
            
            # For most providers, use the 'current' field
            balance = round(balance_data.get("current", 0) * 100) / 100

            if provider in ["AMEX"]:
                pending_transactions = self.get_pending_transactions(card_id)

                # Work in whole pence so charges and credits of either sign add up exactly.
                balance_pence = round(balance * 100)
                pending_pence = [round(txn * 100) for txn in pending_transactions]

                # Separate charges (positive) and payments/refunds (negative)
                pending_charges_pence = sum(p for p in pending_pence if p > 0)
                pending_payments_pence = sum(p for p in pending_pence if p < 0)

                # Amex reports pending charges and pending credits as separate
                # transactions (they are not netted off), so both must be counted,
                # otherwise a pending refund leaves the pot over-funded until it posts.
                pending_balance_pence = pending_charges_pence + pending_payments_pence

                adjusted_balance_pence = balance_pence + pending_balance_pence
                # Pending credits can exceed what is owed (e.g. a refund on a card that
                # is already paid off). The card then owes nothing; a negative figure
                # would eat into the amounts owed on other cards in the total below.
                if adjusted_balance_pence < 0:
                    log.info(
                        f"Amex Card - Pending credits exceed balance (£{adjusted_balance_pence / 100:.2f}); treating as £0.00 owed."
                    )
                    adjusted_balance_pence = 0

                log.info(f"Amex Card - Current Balance (Excluding Pending Transactions): £{balance_pence / 100:.2f}")
                log.info(f"Amex Card - Pending Charges: £{pending_charges_pence / 100:.2f}")
                log.info(f"Amex Card - Pending Payments/Refunds: £{pending_payments_pence / 100:.2f}")
                log.info(f"Amex Card - Pending Balance: £{pending_balance_pence / 100:.2f}")
                log.info(f"Amex Card - Total Balance: £{adjusted_balance_pence / 100:.2f}")
                balance = adjusted_balance_pence / 100

            if provider in ["BARCLAYCARD"]:
                pending_transactions = self.get_pending_transactions(card_id)

                # Separate charges and payments/refunds
                pending_charges = round(sum(txn for txn in pending_transactions if txn > 0) * 100) / 100
                pending_payments = round(sum(txn for txn in pending_transactions if txn < 0) * 100) / 100

                # it looks like pending charges might take into account credits
                pending_balance = pending_charges # + pending_payments

                net_pending = round(sum(pending_transactions) * 100) / 100
                adjusted_balance = balance + net_pending

                log.info(f"Barclaycard Card - Current Balance (Excluding Pending Transactions): £{balance:.2f}")
                log.info(f"Barclaycard Card - Pending Charges: £{pending_charges:.2f}")
                log.info(f"Barclaycard Card - Pending Payments: £{pending_payments:.2f}")
                log.info(f"Barclaycard Card - Pending Balance: £{pending_balance:.2f}")
                log.info(f"Barclaycard Card - True Pending Balance: £{net_pending:.2f}")
                log.info(f"Barclaycard Card - Total Balance: £{adjusted_balance:.2f}")

                # balance = balance
                # lets ensure balances are rounded to whole pence
                balance = round(balance * 100) / 100

            if provider in ["HALIFAX"]:
                # Halifax doesn't provide separate pending transactions
                # The 'available' field already accounts for pending charges
                # Balance owed = credit_limit - available
                credit_limit = balance_data.get("credit_limit", 0)
                available = balance_data.get("available", 0)
                balance_owed = credit_limit - available
                
                log.info(f"Halifax Card - Credit Limit: £{credit_limit:.2f}")
                log.info(f"Halifax Card - Available Credit: £{available:.2f}")
                log.info(f"Halifax Card - Balance Owed: £{balance_owed:.2f}")
                
                # Ensure balance is rounded up and set
                balance = round(balance_owed * 100) / 100

            if provider in ["LLOYDS"]:
                pending_transactions = self.get_pending_transactions(card_id)

                # Separate charges and payments/refunds
                pending_charges = round(sum(txn for txn in pending_transactions if txn > 0) * 100) / 100
                pending_payments = round(sum(txn for txn in pending_transactions if txn < 0) * 100) / 100

                # it looks like pending charges might take into account credits
                pending_balance = pending_charges # + pending_payments

                adjusted_balance = balance + pending_balance

                log.info(f"Lloyds Card - Current Balance (Excluding Pending Transactions): £{balance:.2f}")
                log.info(f"Lloyds Card - Pending Charges: £{pending_charges:.2f}")
                log.info(f"Lloyds Card - Pending Payments: £{pending_payments:.2f}")
                log.info(f"Lloyds Card - Pending Balance: £{pending_balance:.2f}")
                log.info(f"Lloyds Card - Total Balance: £{adjusted_balance:.2f}")
                balance = adjusted_balance

            total_balance += balance

        log.info(f"Total balance calculated: £{total_balance:.2f}")
        # round() rather than int(): int() truncates float noise such as 0.29 * 100
        # == 28.999999999999996 down a penny.
        self._cached_balance = round(total_balance * 100)  # Convert balance to pence
        return self._cached_balance
