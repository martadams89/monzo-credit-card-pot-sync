import logging
from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.domain.settings import Setting
from app.extensions import db, scheduler
from app.models.setting_repository import SqlAlchemySettingRepository
from app.models.account_repository import SqlAlchemyAccountRepository

settings_bp = Blueprint("settings", __name__)

log = logging.getLogger("settings")
repository = SqlAlchemySettingRepository(db)
account_repository = SqlAlchemyAccountRepository(db)

@settings_bp.route("/", methods=["GET"])
def index():
    settings = {s.key: s.value for s in repository.get_all()}
    accounts = account_repository.get_credit_accounts()  # Pass available credit accounts
    return render_template("settings/index.html", data=settings, accounts=accounts)

@settings_bp.route("/", methods=["POST"])
def save():
    try:
        current_settings = {s.key: s.value for s in repository.get_all()}

        # Checkbox: POST request omits unchecked boxes, so set value accordingly
        if request.form.get("enable_sync") is not None:
            repository.save(Setting("enable_sync", "True"))
        else:
            repository.save(Setting("enable_sync", "False"))

        # Checkbox: POST request omits unchecked boxes, so set value accordingly
        if request.form.get("override_cooldown_spending") is not None:
            repository.save(Setting("override_cooldown_spending", "True"))
        else:
            repository.save(Setting("override_cooldown_spending", "False"))

        for key, val in request.form.items():
            if key in ["enable_sync", "override_cooldown_spending"]:
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
    """Clear the deposit cooldown timer for selected or all accounts."""
    try:
        account_type = request.form.get("account_type")
        
        from app.models.cooldown import SqlAlchemyCooldownRepository
        cooldown_repo = SqlAlchemyCooldownRepository(db)
        
        if account_type:
            # Clear cooldown for specific account type
            accounts = account_repository.get_credit_accounts_by_type(account_type)
            for account in accounts:
                cooldown_repo.clear_cooldown(account.id)
            flash(f"Cooldown cleared for {account_type} accounts", "success")
        else:
            # Clear cooldown for all accounts
            accounts = account_repository.get_credit_accounts()
            for account in accounts:
                cooldown_repo.clear_cooldown(account.id)
            flash("Cooldown cleared for all accounts", "success")
            
    except Exception as e:
        log.error("Failed to clear cooldown", exc_info=e)
        flash("Error clearing cooldown", "error")
        
    return redirect(url_for("settings.index"))