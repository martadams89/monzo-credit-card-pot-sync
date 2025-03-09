"""CLI commands for the application."""

import click
import os
from flask import current_app
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User
from app.services.container import container

@click.command('setup-app')
@with_appcontext
def setup_app_command():
    """Set up the application with database and admin user."""
    # Create database tables
    click.echo("Creating database tables...")
    db.create_all()
    click.echo("Database tables created!")
    
    # Create admin user from environment variables
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')
    admin_email = os.environ.get('ADMIN_EMAIL')
    
    if admin_username and admin_password and admin_email:
        click.echo(f"Creating admin user {admin_username}...")
        
        # Check if user already exists
        user = User.query.filter_by(username=admin_username).first()
        if not user:
            user = User(username=admin_username, email=admin_email, is_admin=True)
            user.set_password(admin_password)
            db.session.add(user)
            db.session.commit()
            click.echo("Admin user created!")
        else:
            click.echo("Admin user already exists.")
    else:
        click.echo("Skipping admin user creation (missing environment variables).")
    
    click.echo("Application setup complete!")

def register_commands(app):
    """Register CLI commands with the Flask application."""
    app.cli.add_command(setup_app_command)
