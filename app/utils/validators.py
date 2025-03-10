import re
from datetime import datetime
import pycountry

def validate_email(email):
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password_strength(password):
    """
    Validate password strength.
    
    Password must:
    - Be at least 8 characters long
    - Contain at least one uppercase letter
    - Contain at least one lowercase letter
    - Contain at least one number
    - Contain at least one special character
    
    Args:
        password: Password to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""

def validate_date_format(date_str, format='%Y-%m-%d'):
    """
    Validate date string format.
    
    Args:
        date_str: Date string to validate
        format: Expected date format
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        datetime.strptime(date_str, format)
        return True
    except ValueError:
        return False

def validate_currency_code(currency_code):
    """
    Validate if the given string is a valid ISO 4217 currency code.
    
    Args:
        currency_code: Currency code to validate (e.g., 'USD', 'EUR', 'GBP')
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        return currency_code in [currency.alpha_3 for currency in pycountry.currencies]
    except AttributeError:
        # Fallback for common currencies if pycountry is not available
        common_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY']
        return currency_code in common_currencies

def validate_amount(amount, min_value=0, max_value=None):
    """
    Validate if the amount is within acceptable range.
    
    Args:
        amount: Amount to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value (optional)
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        amount_float = float(amount)
        if amount_float < min_value:
            return False
        
        if max_value is not None and amount_float > max_value:
            return False
            
        return True
    except (ValueError, TypeError):
        return False

def validate_percentage(percentage):
    """
    Validate if the percentage is within 0-100 range.
    
    Args:
        percentage: Percentage to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    return validate_amount(percentage, min_value=0, max_value=100)

def sanitize_input(text):
    """
    Sanitize user input to prevent XSS attacks.
    
    Args:
        text: Text to sanitize
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
        
    # Replace potentially dangerous characters
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#x27;")
    
    return text
