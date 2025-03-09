"""
Service for managing baseline data and application state measurements.

This service tracks baselines for account balances, system performance,
and other metrics to detect anomalies and changes over time.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

class BaselineService:
    """Service for managing baseline data and measurements."""
    
    def __init__(self, setting_repository=None):
        """Initialize BaselineService.
        
        Args:
            setting_repository: Repository for application settings
        """
        self.setting_repository = setting_repository
    
    def record_balance_baseline(self, account_id: str, card_balance: int, pot_balance: int) -> bool:
        """Record a baseline for account balances.
        
        Args:
            account_id: Account ID
            card_balance: Credit card balance in pence
            pot_balance: Monzo pot balance in pence
            
        Returns:
            bool: True if successful
        """
        if not self.setting_repository:
            log.error("Setting repository not available")
            return False
        
        try:
            # Get existing baselines
            baselines_json = self.setting_repository.get('balance_baselines', '{}')
            baselines = json.loads(baselines_json)
            
            # Create or update baseline for this account
            timestamp = datetime.utcnow().isoformat()
            
            if account_id not in baselines:
                baselines[account_id] = []
            
            # Add new baseline
            baseline = {
                'timestamp': timestamp,
                'card_balance': card_balance,
                'pot_balance': pot_balance,
                'difference': card_balance - pot_balance
            }
            
            # Add to account baselines (limit to last 10)
            baselines[account_id].append(baseline)
            baselines[account_id] = baselines[account_id][-10:]
            
            # Save updated baselines
            updated_json = json.dumps(baselines)
            return self.setting_repository.save_setting('balance_baselines', updated_json)
            
        except Exception as e:
            log.error(f"Error recording balance baseline: {str(e)}")
            return False
    
    def get_account_baselines(self, account_id: str) -> List[Dict[str, Any]]:
        """Get baseline history for an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            list: Baseline history
        """
        if not self.setting_repository:
            return []
        
        try:
            # Get existing baselines
            baselines_json = self.setting_repository.get('balance_baselines', '{}')
            baselines = json.loads(baselines_json)
            
            # Return account baselines or empty list
            return baselines.get(account_id, [])
            
        except Exception as e:
            log.error(f"Error getting account baselines: {str(e)}")
            return []
    
    def analyze_baseline_trends(self, account_id: str) -> Dict[str, Any]:
        """Analyze trends in baselines for an account.
        
        Args:
            account_id: Account ID
            
        Returns:
            dict: Analysis results
        """
        baselines = self.get_account_baselines(account_id)
        
        if not baselines or len(baselines) < 2:
            return {
                'status': 'insufficient_data',
                'message': 'Not enough baseline data for analysis',
                'stability': None,
                'trend': None
            }
        
        try:
            # Calculate trends
            differences = [b['difference'] for b in baselines]
            abs_differences = [abs(d) for d in differences]
            avg_difference = sum(differences) / len(differences)
            max_difference = max(abs_differences)
            
            # Determine stability (lower is more stable)
            stability_score = max_difference / 10000  # As percentage of £100
            
            # Determine trend direction
            recent_baselines = baselines[-3:]  # Last 3 baselines
            recent_diffs = [b['difference'] for b in recent_baselines]
            
            if all(d > 0 for d in recent_diffs):
                trend = "card_increasing"  # Card balance consistently higher than pot
            elif all(d < 0 for d in recent_diffs):
                trend = "pot_increasing"  # Pot balance consistently higher than card
            else:
                trend = "fluctuating"
            
            return {
                'status': 'ok',
                'message': 'Baseline analysis complete',
                'stability': stability_score,
                'trend': trend,
                'avg_difference': avg_difference,
                'max_difference': max_difference
            }
            
        except Exception as e:
            log.error(f"Error analyzing baseline trends: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error: {str(e)}',
                'stability': None,
                'trend': None
            }
    
    def clear_baselines(self, account_id: Optional[str] = None) -> bool:
        """Clear baseline data.
        
        Args:
            account_id: Optional account ID (clear just this account's data)
            
        Returns:
            bool: True if successful
        """
        if not self.setting_repository:
            return False
        
        try:
            if account_id:
                # Clear just one account's baselines
                baselines_json = self.setting_repository.get('balance_baselines', '{}')
                baselines = json.loads(baselines_json)
                
                if account_id in baselines:
                    del baselines[account_id]
                    updated_json = json.dumps(baselines)
                    return self.setting_repository.save_setting('balance_baselines', updated_json)
                return True  # Account not found, nothing to clear
            else:
                # Clear all baselines
                return self.setting_repository.save_setting('balance_baselines', '{}')
                
        except Exception as e:
            log.error(f"Error clearing baselines: {str(e)}")
            return False
