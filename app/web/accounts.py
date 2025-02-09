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

@accounts_bp.route("/switch", methods=["GET", "POST"])
def switch_account():
    # In GET: render the account-switch form listing available accounts
    if request.method == "GET":
        # Use your provider/service to fetch available accounts.
        # For example, assume current_account is your active MonzoAccount:
        current_account = repository.get("Monzo")
        available_accounts = current_account._fetch_accounts()
        return render_template("accounts/switch_account.html", accounts=available_accounts)

    # In POST: update the account_id based on selection
    elif request.method == "POST":
        selected_account_id = request.form.get("account_id")
        if selected_account_id:
            # Update the account record
            account = repository.get("Monzo")
            account.account_id = selected_account_id
            repository.save(account)
            flash("Account switched successfully", "success")
        else:
            flash("No account selected", "error")
        return redirect(url_for("accounts.switch_account"))

@accounts_bp.route("/add", methods=["GET"])
def add_account():
    monzo_provider = provider_mapping[AuthProviderType.MONZO]
    credit_providers = dict(
        [
            (i, provider_mapping[i])
            for i in provider_mapping
            if i is not AuthProviderType.MONZO
        ]
    )
    return render_template(
        "accounts/add.html",
        monzo_provider=monzo_provider,
        credit_providers=credit_providers,
    )


@accounts_bp.route("/", methods=["POST"])
def delete_account():
    account_type = request.form["account_type"]
    try:
        account_repository.delete(account_type)
        flash("Account deleted")
    except NoResultFound:
        pass

    return redirect(url_for("accounts.index"))
