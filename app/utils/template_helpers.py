"""Utility functions for Jinja2 templates."""

import logging
from datetime import datetime
from flask import url_for, current_app

logger = logging.getLogger(__name__)

def format_currency(value, currency='GBP'):
    """Format a value as currency.
    
    Args:
        value: The value to format
        currency: The currency code
        
    Returns:
        Formatted currency string
    """
    if value is None:
        return "N/A"
        
    # Convert from decimal (API values are usually in smallest denomination)
    decimal_value = float(value) / 100
    
    # Format based on currency
    if currency == 'GBP':
        return f"£{decimal_value:.2f}"
    elif currency == 'EUR':
        return f"€{decimal_value:.2f}"
    elif currency == 'USD':
        return f"${decimal_value:.2f}"
    else:
        return f"{decimal_value:.2f} {currency}"

def format_datetime(dt, format_str=None):
    """Format a datetime object.
    
    Args:
        dt: The datetime to format
        format_str: Optional format string
        
    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "Never"
        
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
            
    if format_str:
        return dt.strftime(format_str)
    else:
        return dt.strftime('%Y-%m-%d %H:%M:%S')

def relative_time(dt):
    """Format a datetime as a relative time string.
    
    Args:
        dt: The datetime to format
        
    Returns:
        Relative time string (e.g. "2 hours ago")
    """
    if dt is None:
        return "Never"
        
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    
    now = datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime('%Y-%m-%d')

def truncate(text, length=50):
    """Truncate text to a certain length.
    
    Args:
        text: The text to truncate
        length: Maximum length
        
    Returns:
        Truncated text
    """
    if text is None:
        return ""
        
    if len(text) <= length:
        return text
    else:
        return text[:length-3] + "..."

def register_template_filters(app):
    """Register custom template filters with Flask app.
    
    Args:
        app: Flask application instance
    """
    @app.template_filter('formatmoney')
    def formatmoney_filter(value, currency='GBP'):
        return format_currency(value, currency)
    
    @app.template_filter('formatdatetime')
    def formatdatetime_filter(value, format_str=None):
        return format_datetime(value, format_str)
    
    @app.template_filter('relativetime')
    def relativetime_filter(value):
        return relative_time(value)
    
    @app.template_filter('truncate')
    def truncate_filter(value, length=50):
        return truncate(value, length)
        
    @app.template_filter('jsonpretty')
    def jsonpretty_filter(value):
        import json
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value
        return json.dumps(value, indent=2)

def register_template_helpers(app):
    """Register template helpers with the Flask app."""
    
    @app.template_filter('formatdatetime')
    def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
        """Format a datetime object."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                try:
                    value = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ')
                except ValueError:
                    return value
        return value.strftime(format)
    
    @app.template_filter('formatmoney')
    def format_money(value):
        """Format a money amount in the appropriate currency format."""
        if value is None:
            return "£0.00"
        
        # Default to GBP
        symbol = "£"
        
        # Convert to decimal
        pounds = abs(value) / 100
        
        # Format with 2 decimal places
        formatted = f"{symbol}{pounds:.2f}"
        
        # Add negative sign if needed
        if value < 0:
            formatted = f"-{formatted}"
            
        return formatted
    
    @app.template_filter('formatdate')
    def format_date(value):
        """Format a date to a human-readable format."""
        if isinstance(value, datetime):
            return value.strftime('%d %b %Y')
        return str(value)
        
    @app.template_filter('formatdatetime')
    def format_datetime(value):
        """Format a datetime to a human-readable format."""
        if isinstance(value, datetime):
            return value.strftime('%d %b %Y %H:%M')
        return str(value)
    
    @app.template_filter('truncate_hash')
    def truncate_hash(value, length=8):
        """Truncate a hash to a specific length."""
        if not value or not isinstance(value, str):
            return value
        if len(value) <= length * 2:
            return value
        return value[:length] + '...' + value[-length:]
    
    @app.template_filter('tojson')
    def to_json(value):
        """Convert value to JSON for use in JavaScript."""
        import json
        return json.dumps(value)
    
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates."""
        return {
            'current_year': datetime.now().year
        }
    
    # Add a new helper to check if a route exists
    @app.template_test('route_exists')
    def route_exists(endpoint):
        """Check if a route exists in the Flask app."""
        try:
            from flask import current_app
            return endpoint in current_app.url_map._rules_by_endpoint
        except:
            return False
