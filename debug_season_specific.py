#!/usr/bin/env python3
"""
Debug script to test season-specific API calls
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

async def debug_season_specific():
    """Debug season-specific API calls"""
    
    print("=== Debugging Season-Specific API Calls ===")
    
    async with RaiderIO() as rio:
        # Get a character with recent runs
        print("--- Getting character data ---")
        data = await rio.get_character_profile("stonehenge", "deathwing", "us")
        
        if not data:
            print("❌ No character data")
            return
            
        # Get recent runs
        recent_runs = data.get('mythic_plus_recent_runs', [])
        if not recent_runs:
            print("❌ No recent runs")
            return
            
        print(f"✅ Found {len(recent_runs)} recent runs")
        
        # Look at runs and try to determine their seasons from URLs
        for i, run in enumerate(recent_runs[:5]):
            print(f"\n--- Run {i+1}: {run.get('dungeon')} +{run.get('mythic_level')} ---")
            run_id = run.get('keystone_run_id')
            url = run.get('url', '')
            
            # Extract season from URL
            season_from_url = None
            if 'season-tww-2' in url:
                season_from_url = 'season-tww-2'
            elif 'season-tww-3' in url:
                season_from_url = 'season-tww-3'
            elif 'season-tww-1' in url:
                season_from_url = 'season-tww-1'
            
            print(f"Run ID: {run_id}")
            print(f"URL: {url}")
            print(f"Season from URL: {season_from_url}")
            
            if season_from_url:
                print(f"\nTrying API call with season: {season_from_url}")
                
                # Try direct API call with the correct season
                async with aiohttp.ClientSession() as session:
                    api_url = f"{config.RAIDERIO_API_URL}/mythic-plus/run-details"
                    params = {
                        "id": run_id,
                        "season": season_from_url
                    }
                    
                    try:
                        async with session.get(api_url, params=params) as response:
                            if response.status == 200:
                                detailed_data = await response.json()
                                print(f"✅ SUCCESS! Got detailed data with {season_from_url}")
                                print(f"Keys: {list(detailed_data.keys())}")
                                
                                if 'roster' in detailed_data:
                                    roster = detailed_data['roster']
                                    print(f"✅ ROSTER FOUND! {len(roster)} members:")
                                    for member in roster:
                                        char = member.get('character', {})
                                        name = char.get('name', 'Unknown')
                                        realm = char.get('realm', {}).get('name', 'Unknown')
                                        spec = char.get('spec', {}).get('name', 'Unknown')
                                        class_name = char.get('class', {}).get('name', 'Unknown')
                                        role = char.get('spec', {}).get('role', 'Unknown')
                                        print(f"  - {name}-{realm} ({spec} {class_name}) [{role}]")
                                    
                                    # This is the data we want!
                                    print("\n🎉 FOUND THE SOLUTION!")
                                    print("The issue is that we need to use the correct season for each run!")
                                    return
                                else:
                                    print("❌ No roster in detailed data")
                                    print("Available keys:", list(detailed_data.keys()))
                            else:
                                error_text = await response.text()
                                print(f"❌ API failed: {response.status} - {error_text}")
                    except Exception as e:
                        print(f"❌ API error: {e}")
            else:
                print("❌ Could not determine season from URL")
        
        print("\n" + "="*60)
        print("CONCLUSION:")
        print("The runs are from different seasons, and we need to use the")
        print("correct season parameter for each run to get roster data!")

if __name__ == "__main__":
    asyncio.run(debug_season_specific())
