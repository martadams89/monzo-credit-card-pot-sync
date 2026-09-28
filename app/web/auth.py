from time import time

from flask import Blueprint, flash, redirect, request, session, url_for
from sqlalchemy.exc import NoResultFound

from app.domain.accounts import MonzoAccount, TrueLayerAccount
from app.domain.auth_providers import (
    AuthProviderType,
    MonzoAuthProvider,
    provider_mapping,
)
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository

auth_bp = Blueprint("auth", __name__)

account_repository = SqlAlchemyAccountRepository(db)


@auth_bp.route("/callback/monzo", methods=["GET"])
def monzo_callback():
    code = request.args.get("code")
    tokens = MonzoAuthProvider().handle_oauth_code_callback(code)

    account = MonzoAccount(
        tokens["access_token"],
        tokens["refresh_token"],
        int(time()) + tokens["expires_in"],
        pot_id="default_pot"  # Provide a default pot ID
    )
    account_repository.save(account)

    flash(f"Successfully linked {account.type}")
    return redirect(url_for("accounts.index"))


@auth_bp.route("/callback/truelayer", methods=["GET"])
def truelayer_callback():
    provider_type = request.args.get("state", "").rsplit("-", 1)[0]
    provider = provider_mapping[AuthProviderType(provider_type)]

    code = request.args.get("code")
    tokens = provider.handle_oauth_code_callback(code)
    token_expiry = int(time()) + tokens["expires_in"]

    # Reconnecting an existing card (Accounts > Reconnect) keeps the connection,
    # its pot and its settings, and only swaps in the new tokens.
    reconnect = session.pop("reconnect", None) or {}
    reconnect_type = reconnect.get("account") if reconnect.get("state") == request.args.get("state") else None
    if reconnect_type:
        try:
            existing = account_repository.get(reconnect_type)
            if existing.provider_type == provider.name:
                account_repository.update_tokens(
                    existing.type, tokens["access_token"], tokens["refresh_token"], token_expiry
                )
                flash(f"Reconnected {existing.type}")
                return redirect(url_for("accounts.index"))
        except NoResultFound:
            pass

    account_name = account_repository.get_next_account_name(provider.name)
    account = TrueLayerAccount(
        account_name,
        tokens["access_token"],
        tokens["refresh_token"],
        token_expiry,
        pot_id="default_pot",
        provider_type=provider.name,
    )
    account_repository.save(account)

    flash(f"Successfully linked {account.type}")
    return redirect(url_for("accounts.index"))
