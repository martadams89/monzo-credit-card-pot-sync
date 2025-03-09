"""Service for handling serialization of complex objects."""

import json
from datetime import datetime, date
import decimal
from app.utils.json_utils import DateTimeEncoder

class SerializationService:
    """Service for serialization of complex application objects."""
    
    def __init__(self):
        self.encoder = DateTimeEncoder()
        
    def to_json(self, obj, **kwargs):
        """Convert an object to a JSON string.
        
        Args:
            obj: Object to serialize
            **kwargs: Additional arguments for json.dumps
            
        Returns:
            str: JSON string
        """
        return json.dumps(obj, cls=DateTimeEncoder, **kwargs)
        
    def from_json(self, json_str, **kwargs):
        """Convert a JSON string back to an object.
        
        Args:
            json_str: JSON string to deserialize
            **kwargs: Additional arguments for json.loads
            
        Returns:
            object: Deserialized object
        """
        return json.loads(json_str, **kwargs) if json_str else None
