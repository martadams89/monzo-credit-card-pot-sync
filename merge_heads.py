#!/usr/bin/env python
"""Script to merge multiple migration heads."""

import os
import subprocess
import sys

def merge_heads():
    """Merge multiple migration heads into a single head."""
    try:
        print("Checking for migration heads...")
        
        # Set Flask environment
        os.environ["FLASK_APP"] = "run.py"
        
        # Run 'flask db heads' to get current heads
        result = subprocess.run(["flask", "db", "heads"], 
                               capture_output=True, 
                               text=True)
        
        if result.returncode != 0:
            print(f"Error running 'flask db heads': {result.stderr}")
            return False
        
        heads = [line.split(' ')[0] for line in result.stdout.strip().split('\n') if line]
        
        if len(heads) <= 1:
            print("No multiple heads detected. No merge needed.")
            return True
        
        print(f"Found {len(heads)} migration heads: {', '.join(heads)}")
        print("Creating a merge migration...")
        
        # Create a merge migration
        merge_cmd = ["flask", "db", "merge", "-m", "merge_heads"] + heads
        merge_result = subprocess.run(merge_cmd, capture_output=True, text=True)
        
        if merge_result.returncode != 0:
            print(f"Error creating merge migration: {merge_result.stderr}")
            return False
            
        print("Successfully created merge migration.")
        print("Applying migrations...")
        
        # Apply migrations
        upgrade_result = subprocess.run(["flask", "db", "upgrade"], 
                                       capture_output=True, 
                                       text=True)
        
        if upgrade_result.returncode != 0:
            print(f"Error applying migrations: {upgrade_result.stderr}")
            return False
            
        print("Migrations applied successfully.")
        return True
        
    except Exception as e:
        print(f"Error during merge: {str(e)}")
        return False

if __name__ == "__main__":
    if merge_heads():
        print("\nSuccess! Migration heads have been merged.")
    else:
        print("\nFailed to merge migration heads.")
        sys.exit(1)
