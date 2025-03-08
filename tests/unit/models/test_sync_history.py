import pytest
import json
import datetime
from app.models.sync_history import SyncHistory, DateTimeEncoder

def test_sync_history_serializes_datetime():
    """Test that the sync history model can serialize datetime objects"""
    # Create test data with a datetime
    now = datetime.datetime.utcnow()
    test_data = {
        "started_at": now,
        "status": "completed",
        "accounts_processed": [{"account": "test", "status": "success"}]
    }
    
    # Create a sync history object
    history = SyncHistory("completed", test_data)
    
    # Verify that the data was serialized properly
    assert history.data is not None
    
    # Deserialize the data and check the values
    data_dict = json.loads(history.data)
    assert data_dict["status"] == "completed"
    assert data_dict["started_at"] == now.isoformat()  # Should be an ISO-formatted string

def test_sync_history_data_json():
    """Test the data_json property"""
    test_data = {"status": "completed", "value": 123}
    history = SyncHistory("completed", test_data)
    
    # Check that data_json returns the correct dictionary
    assert history.data_json == test_data
