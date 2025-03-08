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
    
    # Add chart data for each account
    for i, data in enumerate(account_data):
        if 'error' not in data:
            try:
                account_type = data['account'].type
                history = history_repository.get_balance_history(account_type, days=30)
                
                dates = []
                card_balances = []
                pot_balances = []
                
                for record in history:
                    dates.append(record['timestamp'].strftime('%Y-%m-%d'))
                    card_balances.append(record['card_balance'])
                    pot_balances.append(record['pot_balance'])
                
                # Add today's values if we have them
                if dates and dates[-1] != datetime.datetime.now().strftime('%Y-%m-%d'):
                    dates.append(datetime.datetime.now().strftime('%Y-%m-%d'))
                    card_balances.append(data['card_balance'])
                    pot_balances.append(data['pot_balance'])
                
                account_data[i]['chart_data'] = {
                    'dates': dates,
                    'card_balances': card_balances,
                    'pot_balances': pot_balances
                }
            except Exception as e:
                log.error(f"Error preparing chart data for {data['account'].type}: {e}")
    
    # Get overview statistics
    total_card_balance = sum([data.get('card_balance', 0) for data in account_data if 'error' not in data])
    total_pot_balance = sum([data.get('pot_balance', 0) for data in account_data if 'error' not in data])
    
    sync_history = history_repository.get_recent_syncs(limit=10)
    
    return render_template(
        "dashboard/index.html",
        accounts=credit_accounts,
        account_data=account_data,
        monzo_account=monzo_account,
        status=status,
        sync_history=sync_history,
        total_card_balance=total_card_balance,
        total_pot_balance=total_pot_balance
    )
