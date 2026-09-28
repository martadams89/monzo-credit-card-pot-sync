import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.domain.settings import Setting
from app.extensions import db, scheduler
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.setting_repository import SqlAlchemySettingRepository

settings_bp = Blueprint("settings", __name__)

log = logging.getLogger("settings")
repository = SqlAlchemySettingRepository(db)

# On/off settings shown as checkboxes; an unchecked box is missing from the form.
CHECKBOX_SETTINGS = ["enable_sync", "override_cooldown_spending"]
# Text settings the form may change. Anything else posted is ignored, so the form
# can't be used to overwrite sign in, 2FA or other internal settings.
TEXT_SETTINGS = [
    "monzo_client_id",
    "monzo_client_secret",
    "truelayer_client_id",
    "truelayer_client_secret",
    "sync_interval_seconds",
    "deposit_cooldown_hours",
    "log_retention_days",
]
# Never sent back to the browser; a blank field keeps the saved value.
SECRET_SETTINGS = ["monzo_client_secret", "truelayer_client_secret"]
account_repository = SqlAlchemyAccountRepository(db)

@settings_bp.route("/", methods=["GET"])
def index():
    settings = {s.key: s.value for s in repository.get_all()}
    data = {key: settings.get(key) for key in TEXT_SETTINGS + CHECKBOX_SETTINGS if key not in SECRET_SETTINGS}
    secrets_saved = {key: bool(settings.get(key)) for key in SECRET_SETTINGS}
    accounts = account_repository.get_credit_accounts()  # Pass available credit accounts
    return render_template("settings/index.html", data=data, secrets_saved=secrets_saved, accounts=accounts)

@settings_bp.route("/", methods=["POST"])
def save():
    try:
        current_settings = {s.key: s.value for s in repository.get_all()}

        # Checkbox: POST request omits unchecked boxes, so set value accordingly
        for key in CHECKBOX_SETTINGS:
            repository.save(Setting(key, "True" if request.form.get(key) is not None else "False"))

        for key, val in request.form.items():
            if key not in TEXT_SETTINGS:
                continue
            if key in SECRET_SETTINGS and val == "":
                continue

            if current_settings.get(key) != val:
                repository.save(Setting(key, val))

                if key == "sync_interval_seconds":
                    scheduler.modify_job(id="sync_balance", trigger="interval", seconds=int(val))

        flash("Settings saved")
    except Exception as e:
        log.error("Failed to save settings", exc_info=e)
        flash("Error saving settings", "error")

    return redirect(url_for("settings.index"))

@settings_bp.route("/clear_cooldown", methods=["POST"])
def clear_cooldown():
    # Clear cooldown
    monzo_account = account_repository.get_monzo_account()  # get the MonzoAccount for pot balance
    selected_type = request.form.get("account_type")
    if selected_type:
        credit_accounts = [
            acct for acct in account_repository.get_credit_accounts()
            if acct.type == selected_type
        ]
    else:
        credit_accounts = account_repository.get_credit_accounts()
    for account in credit_accounts:
        account.cooldown_until = None
        # Use the monzo_account to retrieve the pot balance
        new_baseline = monzo_account.get_pot_balance(account.pot_id)
        account.prev_balance = new_baseline
        account = account_repository.update_credit_account_fields(account.type, account.pot_id, new_baseline, None)
    flash("Cooldown cleared—baseline updated for selected account(s).")
    return redirect(url_for("settings.index"))