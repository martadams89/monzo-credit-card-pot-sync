import click
import os
import uuid
from datetime import datetime
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.user import User, Role
from app.models.monzo import MonzoAccount, MonzoPot, SyncRule
from app.services.sync_service import SyncService
from app.utils.backup import create_backup, restore_from_backup, create_database_backup
from app.models.user_repository import SqlAlchemyUserRepository

@click.command('create-user')
@click.option('--username', prompt=True, help='Username for the new user')
@click.option('--email', prompt=True, help='Email address for the new user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the new user')
@click.option('--admin', is_flag=True, help='Create the user as an admin')
@with_appcontext
def create_user_command(username, email, password, admin):
    """Create a new user."""
    role = Role.ADMIN if admin else Role.USER
    
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email.lower(),
        password_hash=generate_password_hash(password),
        is_active=True,
        role=role.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.session.add(user)
    db.session.commit()
    
    click.echo(f"User {username} created successfully with ID {user.id}")
    if admin:
        click.echo("User has admin privileges")

@click.command('run-sync')
@click.option('--rule-id', type=int, help='Specific rule ID to run, or all rules if not specified')
@with_appcontext
def run_sync_command(rule_id):
    """Run sync rules manually."""
    sync_service = SyncService()
    
    if rule_id:
        # Run a specific rule
        result = sync_service.sync_credit_card_balance(rule_id)
        if result:
            click.echo(f"Rule {rule_id} executed successfully: {result.details}")
        else:
            click.echo(f"Rule {rule_id} execution failed or had no transfers to make")
    else:
        # Run all active rules
        results = sync_service.execute_all_active_rules()
        click.echo(f"Executed {len(results)} sync rules")
        for result in results:
            click.echo(f"- {result.details}")

@click.command('create-backup')
@click.option('--include-data/--no-data', default=True, help='Include database data')
@click.option('--include-config/--no-config', default=True, help='Include configuration files')
@click.option('--output', help='Output directory (defaults to backup_dir in config)')
@with_appcontext
def create_backup_command(include_data, include_config, output):
    """Create a backup of the application."""
    backup_file = create_backup(include_data=include_data, include_config=include_config, output_dir=output)
    click.echo(f"Backup created: {backup_file}")

@click.command('restore-backup')
@click.argument('backup_file', type=click.Path(exists=True))
@click.option('--restore-data/--no-data', default=True, help='Restore database data')
@click.option('--restore-config/--no-config', default=True, help='Restore configuration files')
@with_appcontext
def restore_backup_command(backup_file, restore_data, restore_config):
    """Restore a backup of the application."""
    result = restore_from_backup(backup_file, restore_data=restore_data, restore_config=restore_config)
    if result:
        click.echo("Backup restored successfully")
    else:
        click.echo("Backup restoration failed")

@click.command('reset-password')
@click.option('--email', prompt=True, help='Email address of the user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='New password')
@with_appcontext
def reset_password_command(email, password):
    """Reset a user's password."""
    user_repo = SqlAlchemyUserRepository(db)
    user = user_repo.get_by_email(email)
    
    if not user:
        click.echo(f"No user found with email {email}")
        return
    
    user.password_hash = generate_password_hash(password)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    
    click.echo(f"Password reset successfully for user {user.username}")

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database (tables and initial data)."""
    click.echo('Initializing the database...')
    
    # Create all tables
    db.create_all()
    
    click.echo('Database initialized successfully!')

@click.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@with_appcontext
def create_admin_user(username, email, password):
    """Create an admin user."""
    try:
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            click.echo(f"User '{username}' already exists.")
            return
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            click.echo(f"Email '{email}' already registered.")
            return
        
        # Create admin user
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email.lower(),
            password_hash=generate_password_hash(password),
            role=Role.ADMIN.value,
            is_active=True,
            email_verified_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f"Admin user '{username}' created successfully!")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating admin user: {str(e)}")

@click.command('backup-db')
@click.option('--output-dir', default=None, help='Directory to store the backup file')
@with_appcontext
def backup_database(output_dir):
    """Create a backup of the database."""
    if not output_dir:
        output_dir = current_app.config.get('BACKUP_DIR', 'backups')
    
    try:
        # Ensure backup directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Create backup
        backup_file = create_database_backup(output_dir)
        
        if backup_file:
            click.echo(f"Database backup created: {backup_file}")
        else:
            click.echo("Backup failed.")
            
    except Exception as e:
        click.echo(f"Error creating backup: {str(e)}")

def register_commands(app):
    """Register CLI commands with the app."""
    app.cli.add_command(create_user_command)
    app.cli.add_command(run_sync_command)
    app.cli.add_command(create_backup_command)
    app.cli.add_command(restore_backup_command)
    app.cli.add_command(reset_password_command)
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_user)
    app.cli.add_command(backup_database)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(create_test_data_command)
    app.cli.add_command(cleanup_command)

@click.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option('--email', prompt=True, help='Admin email')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@with_appcontext
def create_admin_command(username, email, password):
    """Create an admin user."""
    try:
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            click.echo(f'User with username {username} or email {email} already exists.')
            return
            
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            is_active=True,
            is_email_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {username} created successfully.')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating admin user: {str(e)}')

@click.command('create-test-data')
@with_appcontext
def create_test_data_command():
    """Create test data for development."""
    from app.models.monzo import MonzoAccount, MonzoPot, SyncRule
    from app.models.user import User
    import uuid
    from datetime import datetime, timedelta
    
    try:
        # Create test user if not exists
        test_user = User.query.filter_by(email='test@example.com').first()
        if not test_user:
            test_user = User(
                id=str(uuid.uuid4()),
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password'),
                role='user',
                is_active=True,
                is_email_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(test_user)
            db.session.commit()
            click.echo('Created test user: testuser / password')
            
        # Create test Monzo account
        test_account = MonzoAccount.query.filter_by(user_id=test_user.id).first()
        if not test_account:
            test_account = MonzoAccount(
                id=str(uuid.uuid4()),
                user_id=test_user.id,
                name='Test Monzo Account',
                type='monzo',
                account_id='acc_test123',
                access_token='test_access_token',
                refresh_token='test_refresh_token',
                token_expires_at=datetime.utcnow() + timedelta(hours=1),
                balance=10000,  # £100.00
                currency='GBP',
                is_active=True,
                sync_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(test_account)
            db.session.commit()
            click.echo('Created test Monzo account')
            
        # Create test pots
        if not MonzoPot.query.filter_by(account_id=test_account.id).first():
            savings_pot = MonzoPot(
                id=str(uuid.uuid4()),
                account_id=test_account.id,
                name='Savings Pot',
                pot_id='pot_savings123',
                balance=5000,  # £50.00
                currency='GBP',
                is_locked=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            credit_card_pot = MonzoPot(
                id=str(uuid.uuid4()),
                account_id=test_account.id,
                name='Credit Card Pot',
                pot_id='pot_cc123',
                balance=2000,  # £20.00
                currency='GBP',
                is_locked=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add_all([savings_pot, credit_card_pot])
            db.session.commit()
            click.echo('Created test pots')
            
            # Create test sync rule
            rule = SyncRule(
                id=str(uuid.uuid4()),
                user_id=test_user.id,
                name='Credit Card Payment Rule',
                source_account_id=test_account.id,
                target_pot_id=credit_card_pot.id,
                trigger_type='daily',
                action_type='transfer_amount',
                action_amount=1000,  # £10.00
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(rule)
            db.session.commit()
            click.echo('Created test sync rule')
            
        click.echo('Test data created successfully')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating test data: {str(e)}')

@click.command('cleanup')
@click.option('--confirm', is_flag=True, help='Confirm cleanup operation')
@with_appcontext
def cleanup_command(confirm):
    """Cleanup old data (sync history, logs, etc.)."""
    if not confirm:
        click.echo('This will remove old sync history and logs. Use --confirm to proceed.')
        return
        
    try:
        from app.models.monzo import SyncHistory
        from datetime import datetime, timedelta
        
        # Delete sync history older than 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        deleted = db.session.query(SyncHistory).filter(SyncHistory.created_at < thirty_days_ago).delete()
        
        db.session.commit()
        click.echo(f'Deleted {deleted} old sync history records.')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error during cleanup: {str(e)}')
