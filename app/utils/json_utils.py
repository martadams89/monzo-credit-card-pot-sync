"""
JSON utilities for handling advanced serialization needs.

This module provides enhanced JSON serialization/deserialization,
particularly handling datetime objects and other special types.
"""

import json
import logging
from datetime import datetime, date

log = logging.getLogger(__name__)

def _json_serial(obj):
    """JSON serializer for objects not serializable by default JSON encoder.
    
    Args:
        obj: Object to serialize
        
    Returns:
        str: String representation of the object
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # Handle other special types
    try:
        return str(obj)
    except:
        return "UNSERIALIZABLE_OBJECT"

def dumps(data, **kwargs):
    """Enhanced JSON dumps with handling for special types.
    
    Args:
        data: Data to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        str: JSON string
    """
    try:
        return json.dumps(data, default=_json_serial, **kwargs)
    except Exception as e:
        log.error(f"Error serializing to JSON: {str(e)}")
        
        # Try again with a simplified version
        try:
            # Create a simplified version of the data
            if isinstance(data, dict):
                simple_data = {str(k): str(v) for k, v in data.items()}
            elif isinstance(data, list):
                simple_data = [str(item) for item in data]
            else:
                simple_data = str(data)
                
            return json.dumps(simple_data)
        except:
            # Last resort
            return '{"error": "Serialization failed"}'

def loads(json_str, **kwargs):
    """Enhanced JSON loads with error handling.
    
    Args:
        json_str: JSON string to parse
        **kwargs: Additional arguments to pass to json.loads
        
    Returns:
        object: Parsed JSON data
        
    Raises:
        json.JSONDecodeError: If parsing fails
    """
    if not json_str:
        return {}
        
    # Try to parse the JSON string
    return json.loads(json_str, **kwargs)

def parse_date(date_str):
    """Parse a date or datetime string into a Python datetime object.
    
    Args:
        date_str: Date string in ISO format
        
    Returns:
        datetime: Parsed datetime or None if parsing fails
    """
    if not date_str:
        return None
        
    try:
        try:
            # Try parsing with microseconds
            return datetime.fromisoformat(date_str)
        except ValueError:
            # Try common ISO 8601 format with Z
            if date_str.endswith('Z'):
                return datetime.fromisoformat(date_str[:-1].replace('T', ' '))
                
        # Try other formats
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
                
        log.warning(f"Failed to parse date string: {date_str}")
        return None
    except Exception as e:
        log.error(f"Error parsing date {date_str}: {str(e)}")
        return None
