#!/usr/bin/env python3
"""
Debug script to investigate why we're not getting full group roster data
"""
import asyncio
import aiohttp
import json
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from raiderio_api import RaiderIO

async def debug_group_data():
    """Debug why we're not getting full group roster data"""
    
    print("=== Debugging Group Roster Data ===")
    
    async with RaiderIO() as rio:
        # Get a character with recent runs
        print("--- Getting character data ---")
        data = await rio.get_character_profile("stonehenge", "deathwing", "us")
        
        if not data:
            print("❌ No character data")
            return
            
        print(f"✅ Character: {data.get('name')} - {data.get('realm')}")
        
        # Get recent runs
        recent_runs = data.get('mythic_plus_recent_runs', [])
        if not recent_runs:
            print("❌ No recent runs")
            return
            
        print(f"✅ Found {len(recent_runs)} recent runs")
        
        # Look at the first few runs
        for i, run in enumerate(recent_runs[:3]):
            print(f"\n--- Run {i+1}: {run.get('dungeon')} +{run.get('mythic_level')} ---")
            run_id = run.get('keystone_run_id')
            print(f"Run ID: {run_id}")
            print(f"URL: {run.get('url', 'No URL')}")
            
            # Check what data is in the basic run
            print("Basic run data keys:", list(run.keys()))
            
            # Try to get detailed run information using different approaches
            print("\n1. Testing current get_mythic_plus_run method:")
            detailed_run = await rio.get_mythic_plus_run(run_id)
            if detailed_run:
                print(f"✅ Got detailed data! Keys: {list(detailed_run.keys())}")
                if 'roster' in detailed_run:
                    roster = detailed_run['roster']
                    print(f"✅ Roster found with {len(roster)} members")
                    for member in roster:
                        char = member.get('character', {})
                        name = char.get('name', 'Unknown')
                        spec = char.get('spec', {}).get('name', 'Unknown')
                        print(f"  - {name} ({spec})")
                else:
                    print("❌ No roster in detailed data")
                    print("Available keys:", list(detailed_run.keys()))
            else:
                print("❌ No detailed data returned")
            
            # Try direct API call without season parameter
            print("\n2. Testing direct API call without season:")
            async with aiohttp.ClientSession() as session:
                url = f"{config.RAIDERIO_API_URL}/mythic-plus/run-details"
                params = {"id": run_id}
                
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            direct_data = await response.json()
                            print(f"✅ Direct API success! Keys: {list(direct_data.keys())}")
                            if 'roster' in direct_data:
                                roster = direct_data['roster']
                                print(f"✅ Direct API roster found with {len(roster)} members")
                            else:
                                print("❌ No roster in direct API data")
                        else:
                            error_text = await response.text()
                            print(f"❌ Direct API failed: {response.status} - {error_text}")
                except Exception as e:
                    print(f"❌ Direct API error: {e}")
            
            # Try with different season parameters
            print("\n3. Testing with different season parameters:")
            for season in [None, config.CURRENT_SEASON, "current"]:
                print(f"  Testing season: {season}")
                test_run = await rio.get_mythic_plus_run(run_id, season)
                if test_run and 'roster' in test_run:
                    print(f"    ✅ Found roster with season '{season}'!")
                    break
                else:
                    print(f"    ❌ No roster with season '{season}'")
            
            # Try the character profile with more fields
            print("\n4. Testing character profile with extended fields:")
            extended_fields = "mythic_plus_recent_runs,mythic_plus_scores_by_season:current,mythic_plus_best_runs,mythic_plus_alternate_runs"
            extended_data = await rio.get_character_profile("stonehenge", "deathwing", "us", extended_fields)
            if extended_data:
                extended_runs = extended_data.get('mythic_plus_recent_runs', [])
                if extended_runs:
                    first_extended = extended_runs[0]
                    print(f"Extended run keys: {list(first_extended.keys())}")
                    if 'roster' in first_extended:
                        print("✅ Found roster in extended character data!")
                    else:
                        print("❌ No roster in extended character data")
            
            print("\n" + "="*50)
            break  # Only test the first run for now

if __name__ == "__main__":
    asyncio.run(debug_group_data())
