#!/usr/bin/env python3
"""
Fix Season 3 tracking by resetting run IDs for all players
"""
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Database

def fix_season3_tracking():
    """Reset run IDs for all players to enable Season 3 tracking"""
    
    print("=== Fixing Season 3 Tracking ===")
    print("This will reset the last run ID for all tracked players to 0")
    print("so that Season 3 runs will be detected as new runs.")
    print()
    
    # Initialize database
    db = Database()
    
    try:
        # Get all tracked players
        players = db.get_all_players()
        
        if not players:
            print("❌ No players are being tracked!")
            return
        
        print(f"Found {len(players)} tracked players:")
        for player in players:
            print(f"  - {player['name']}-{player['realm']} ({player['region']})")
            print(f"    Current last run ID: {player['last_run_id']}")
        
        print()
        response = input("Do you want to reset all run IDs to 0? (y/N): ")
        
        if response.lower() != 'y':
            print("❌ Operation cancelled")
            return
        
        print("\n🔧 Resetting run IDs...")
        
        # Reset run IDs for all players
        for player in players:
            success = db.update_player_last_run(player['id'], 0)
            if success:
                print(f"✅ Reset {player['name']}-{player['realm']} to run ID 0")
            else:
                print(f"❌ Failed to reset {player['name']}-{player['realm']}")
        
        print("\n🎉 Season 3 tracking fix complete!")
        print("The bot will now detect Season 3 runs as new runs.")
        print("You may want to restart the bot to see immediate results.")
        
    finally:
        db.close()

if __name__ == "__main__":
    fix_season3_tracking()
