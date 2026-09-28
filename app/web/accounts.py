from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import NoResultFound

from app.domain.auth_providers import AuthProviderType, provider_mapping
from app.extensions import db
from app.models.account_repository import SqlAlchemyAccountRepository

accounts_bp = Blueprint("accounts", __name__)

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

    return render_template("accounts/index.html", accounts=accounts)


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


@accounts_bp.route("/", methods=["POST"])
def delete_account():
    account_type = request.form["account_type"]
    # Deleting an account that is not connected is a no-op.
    account_repository.delete(account_type)
    flash("Account deleted")

    return redirect(url_for("accounts.index"))