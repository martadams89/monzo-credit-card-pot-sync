"""Settings blueprint routes"""

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.settings import settings_bp
from app.extensions import db
from app.models.setting_repository import SqlAlchemySettingRepository
from app.settings.forms import EmailSettingsForm
from app.domain.settings import Setting

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Settings index page"""
    # ... existing code ...
    
    return render_template('settings/index.html', data=settings)

@settings_bp.route('/email', methods=['GET', 'POST'])
@login_required
def email_settings():
    """Email settings page"""
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('dashboard.index'))
        
    setting_repository = SqlAlchemySettingRepository(db)
    form = EmailSettingsForm()
    
    # Pre-fill form with existing settings
    if request.method == 'GET':
        form.email_smtp_server.data = setting_repository.get('email_smtp_server', '')
        form.email_smtp_port.data = int(setting_repository.get('email_smtp_port', 587))
        form.email_smtp_username.data = setting_repository.get('email_smtp_username', '')
        form.email_smtp_password.data = setting_repository.get('email_smtp_password', '')
        form.email_from_address.data = setting_repository.get('email_from_address', '')
        form.email_use_tls.data = setting_repository.get('email_use_tls', 'True') == 'True'
    
    if form.validate_on_submit():
        # Save email settings
        setting_repository.save(Setting('email_smtp_server', form.email_smtp_server.data))
        setting_repository.save(Setting('email_smtp_port', str(form.email_smtp_port.data)))
        setting_repository.save(Setting('email_smtp_username', form.email_smtp_username.data))
        setting_repository.save(Setting('email_smtp_password', form.email_smtp_password.data))
        setting_repository.save(Setting('email_from_address', form.email_from_address.data))
        setting_repository.save(Setting('email_use_tls', str(form.email_use_tls.data)))
        
        flash('Email settings updated successfully.', 'success')
        return redirect(url_for('settings.email_settings'))
        
    return render_template('settings/email.html', form=form)
