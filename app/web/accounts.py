from time import time
from urllib.parse import parse_qs, urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import NoResultFound

from app.domain.auth_providers import AuthProviderType, provider_mapping
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository

accounts_bp = Blueprint("accounts", __name__)

# A month; longer cooldowns would leave real spending unfunded for too long.
MAX_COOLDOWN_HOURS = 720

account_repository = SqlAlchemyAccountRepository(db)


@accounts_bp.route("/", methods=["GET"])
def index():
    # fetch separately so we can always place Monzo first in the list
    accounts = account_repository.get_credit_accounts()
    try:
        monzo_account = account_repository.get_monzo_account()
        accounts.insert(0, monzo_account)
    except NoResultFound:
        pass

    return render_template(
        "accounts/index.html",
        accounts=accounts,
        card_types={account.type for account in accounts if account.type != "Monzo"},
        default_cooldown_hours=_default_cooldown_hours(),
        now=int(time()),
    )


def _default_cooldown_hours():
    from app import security

    return security.get_setting("deposit_cooldown_hours", 3)


@accounts_bp.route("/add", methods=["GET"])
def add_account():
    monzo_provider = provider_mapping[AuthProviderType.MONZO]
    credit_providers = {
        i: provider_mapping[i]
        for i in provider_mapping
        if i is not AuthProviderType.MONZO
    }
    return render_template(
        "accounts/add.html",
        monzo_provider=monzo_provider,
        credit_providers=credit_providers,
    )


@accounts_bp.route("/pending_credits", methods=["POST"])
def set_pending_credits():
    account_type = request.form["account_type"]
    # A checkbox is left out of the form when unchecked.
    include = request.form.get("include_pending_credits") is not None
    try:
        account_repository.set_include_pending_credits(account_type, include)
        state = "counted" if include else "no longer counted"
        flash(f"Pending refunds and payments are {state} for {account_type}")
    except NoResultFound:
        flash("Account not found", "error")

    return redirect(url_for("accounts.index"))


@accounts_bp.route("/cooldown", methods=["POST"])
def set_cooldown_hours():
    account_type = request.form["account_type"]
    value = request.form.get("cooldown_hours", "").strip()
    if value == "":
        hours = None
    else:
        try:
            hours = int(value)
        except ValueError:
            hours = 0
        if not 1 <= hours <= MAX_COOLDOWN_HOURS:
            flash(f"Cooldown must be between 1 and {MAX_COOLDOWN_HOURS} hours", "error")
            return redirect(url_for("accounts.index"))
    try:
        account_repository.set_cooldown_hours(account_type, hours)
        if hours is None:
            flash(f"{account_type} now uses the default cooldown")
        else:
            flash(f"{account_type} cooldown set to {hours} hours")
    except NoResultFound:
        flash("Account not found", "error")
    return redirect(url_for("accounts.index"))


@accounts_bp.route("/reconnect/<path:account_type>", methods=["GET"])
def reconnect(account_type):
    """Re-authorise an existing card connection, keeping its pot and settings."""
    try:
        account = account_repository.get(account_type)
        if account.type == "Monzo":
            raise KeyError(account.type)
        provider = provider_mapping[AuthProviderType(account.provider_type)]
    except (NoResultFound, ValueError, KeyError):
        flash("Account not found", "error")
        return redirect(url_for("accounts.index"))
    oauth_url = provider.create_oauth_request_url()
    # Tie the reconnect to this sign-in attempt's OAuth state, so an abandoned
    # reconnect can never be picked up by a later "Add account".
    state = parse_qs(urlparse(oauth_url).query).get("state", [""])[0]
    session["reconnect"] = {"account": account.type, "state": state}
    return redirect(oauth_url)


@accounts_bp.route("/", methods=["POST"])
def delete_account():
    account_type = request.form["account_type"]
    # Deleting an account that is not connected is a no-op.
    account_repository.delete(account_type)
    flash("Account deleted")

    return redirect(url_for("accounts.index"))