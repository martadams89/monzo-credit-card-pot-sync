import logging
from flask import Blueprint, render_template
from app.models.account_repository import SqlAlchemyAccountRepository
from app.models.sync_history_repository import SqlAlchemySyncHistoryRepository
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository
from time import time
import datetime

dashboard_bp = Blueprint("dashboard", __name__)
log = logging.getLogger("dashboard")
account_repository = SqlAlchemyAccountRepository(db)
history_repository = SqlAlchemySyncHistoryRepository(db)
settings_repository = SqlAlchemySettingRepository(db)

@dashboard_bp.route("/", methods=["GET"])
def index():
    credit_accounts = account_repository.get_credit_accounts()
    monzo_account = None
    try:
        monzo_account = account_repository.get_monzo_account()
    except Exception:
        pass
    
    # Get sync status
    sync_enabled = settings_repository.get("enable_sync") == "True"
    sync_interval = int(settings_repository.get("sync_interval_seconds") or 120)
    
    status = {
        "is_active": sync_enabled,
        "interval": sync_interval,
        "next_sync": datetime.datetime.now() + datetime.timedelta(seconds=sync_interval)
    }
    
    # Prepare account data for display
    account_data = []
    now = int(time())
    
    for account in credit_accounts:
        if monzo_account and account.pot_id:
            try:
                card_balance = account.get_total_balance(force_refresh=False)
                pot_balance = monzo_account.get_pot_balance(account.pot_id)
                
                cooldown_active = account.cooldown_until and account.cooldown_until > now
                cooldown_expires = None
                if cooldown_active:
                    cooldown_expires = datetime.datetime.fromtimestamp(account.cooldown_until)
                
                account_data.append({
                    "account": account,
                    "card_balance": card_balance,
                    "pot_balance": pot_balance,
                    "cooldown_active": cooldown_active,
                    "cooldown_expires": cooldown_expires,
                    "sync_percentage": int(min(100, (pot_balance / card_balance * 100) if card_balance > 0 else 0))
                })
            except Exception as e:
                log.error(f"Error preparing account data for {account.type}: {e}")
                account_data.append({
                    "account": account,
                    "error": str(e)
                })
    
    return render_template(
        "dashboard/index.html",
        accounts=credit_accounts,
        account_data=account_data,
        monzo_account=monzo_account,
        status=status
    )
