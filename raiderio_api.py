import aiohttp
import asyncio
import json
from datetime import datetime
import config

# Import current season information from raiderio_dungeons
# This ensures we're using the same season information everywhere
from raiderio_dungeons import CURRENT_SEASON

class RaiderIO:
    def __init__(self, base_url=config.RAIDERIO_API_URL):
        """Initialize the Raider.io API client"""
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        """Create session when used as async context manager"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session when exiting async context manager"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_character_profile(self, name, realm, region='us', fields=None):
        """Get character profile from Raider.io API"""
        if fields is None:
            # Use the current season for scores
            fields = f"mythic_plus_recent_runs,mythic_plus_scores_by_season:{CURRENT_SEASON}"

        endpoint = f"{self.base_url}/characters/profile"
        params = {
            "region": region,
            "realm": realm,
            "name": name,
            "fields": fields
        }

        return await self._make_request(endpoint, params)

    async def get_character_mythic_plus_runs(self, name, realm, region='us'):
        """Get character mythic+ runs from Raider.io API"""
        fields = f"mythic_plus_recent_runs,mythic_plus_scores_by_season:{CURRENT_SEASON}"
        return await self.get_character_profile(name, realm, region, fields)

    async def get_mythic_plus_run(self, run_id, season=None):
        """Get details for a specific mythic+ run"""
        endpoint = f"{self.base_url}/mythic-plus/run-details"
        params = {"id": run_id}

        # Use the current season if none is specified
        if not season:
            season = CURRENT_SEASON

        params["season"] = season

        return await self._make_request(endpoint, params)

    async def get_run_details(self, run_data):
        """Get detailed information for a run, including roster"""
        # Check if we have a run ID
        run_id = run_data.get("mythic_plus_id") or run_data.get("keystone_run_id")
        if not run_id:
            print("No run ID found in run data")
            return run_data

        print(f"Fetching detailed information for run {run_id}")

        # Try to extract season from the run URL
        season_to_use = None
        run_url = run_data.get("url", "")
        if run_url:
            if "season-tww-3" in run_url:
                season_to_use = "season-tww-3"
            elif "season-tww-2" in run_url:
                season_to_use = "season-tww-2"
            elif "season-tww-1" in run_url:
                season_to_use = "season-tww-1"
            print(f"Extracted season from URL: {season_to_use}")

        # If no season found in URL, try current season first, then fall back to previous seasons
        seasons_to_try = []
        if season_to_use:
            seasons_to_try.append(season_to_use)
        else:
            seasons_to_try = [CURRENT_SEASON, "season-tww-2", "season-tww-1"]
            print(f"No season in URL, will try: {seasons_to_try}")

        # Try each season until we get data
        run_details = None
        for season in seasons_to_try:
            print(f"Trying season: {season}")
            run_details = await self.get_mythic_plus_run(run_id, season)
            if run_details:
                print(f"✅ Got run details with season: {season}")
                break

        if not run_details:
            print(f"No details found for run {run_id} after trying all seasons")
            return run_data

        print(f"Got details for run {run_id}")
        if isinstance(run_details, dict):
            print(f"Run details keys: {run_details.keys()}")

            # Merge the run details with the original run data
            # Keep original data if it's not in the details
            for key, value in run_details.items():
                if key not in run_data or not run_data[key]:
                    run_data[key] = value

            return run_data
        else:
            print(f"Run details is not a dictionary: {type(run_details)}")
            return run_data

    async def _make_request(self, endpoint, params=None):
        """Make a request to the Raider.io API"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(endpoint, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    # Be less noisy about 404 errors for run details - this is expected
                    if response.status == 404 and "run-details" in endpoint:
                        print(f"Run details not available (404) - this is normal for older runs")
                    else:
                        print(f"API Error ({response.status}): {error_text}")
                    return None
        except aiohttp.ClientError as e:
            print(f"Request error: {e}")
            return None

    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    def parse_mythic_plus_runs(self, data):
        """Parse mythic+ runs from API response"""
        if not data:
            print("No data provided to parse_mythic_plus_runs")
            return []

        # Debug the data
        print(f"API response data type: {type(data)}")

        # Handle string data (possibly JSON)
        if isinstance(data, str):
            try:
                data = json.loads(data)
                print("Converted string data to dictionary")
            except Exception as e:
                print(f"Error parsing data as JSON: {e}")
                import traceback
                print(traceback.format_exc())
                return []

        # Check if data is a dictionary
        if not isinstance(data, dict):
            print(f"Data is not a dictionary: {type(data)}")
            return []

        print(f"Data keys: {data.keys()}")

        # Check for mythic_plus_recent_runs in the data
        if "mythic_plus_recent_runs" not in data:
            print("No mythic_plus_recent_runs found in data")
            # Try to find runs in other possible locations
            if "mythic_plus_runs" in data:
                print(f"Found mythic_plus_runs with {len(data['mythic_plus_runs'])} entries")
                return data["mythic_plus_runs"]
            elif "runs" in data:
                print(f"Found runs with {len(data['runs'])} entries")
                return data["runs"]
            else:
                print(f"Available keys in data: {data.keys()}")

                # Try to look for runs in nested structures
                for key in data.keys():
                    if isinstance(data[key], dict) and "runs" in data[key]:
                        print(f"Found runs in nested key {key}")
                        return data[key]["runs"]
                    elif isinstance(data[key], list) and len(data[key]) > 0:
                        print(f"Found list in key {key} with {len(data[key])} items")
                        # Check if the list contains dictionaries with run information
                        if all(isinstance(item, dict) and "dungeon" in item for item in data[key]):
                            print(f"List in key {key} appears to contain run information")
                            return data[key]

                return []

        print(f"Found mythic_plus_recent_runs with {len(data['mythic_plus_recent_runs'])} entries")

        # Debug the first run
        if data["mythic_plus_recent_runs"] and len(data["mythic_plus_recent_runs"]) > 0:
            first_run = data["mythic_plus_recent_runs"][0]
            if isinstance(first_run, dict):
                print(f"First run keys: {first_run.keys()}")
                if "dungeon" in first_run:
                    dungeon = first_run["dungeon"]
                    if isinstance(dungeon, dict):
                        print(f"Dungeon: {dungeon.get('name')}")
                    else:
                        print(f"Dungeon is not a dictionary: {type(dungeon)}")
                print(f"Mythic level: {first_run.get('mythic_level')}")
                print(f"Completed at: {first_run.get('completed_at')}")
                print(f"Run ID: {first_run.get('mythic_plus_id')}")
            else:
                print(f"First run is not a dictionary: {type(first_run)}")

        return data["mythic_plus_recent_runs"]

    def get_latest_run(self, runs):
        """Get the latest run from a list of runs"""
        if not runs:
            print("No runs provided to get_latest_run")
            return None

        # Debug the runs data
        print(f"Runs data type: {type(runs)}")
        print(f"Number of runs: {len(runs) if isinstance(runs, list) else 'not a list'}")

        if isinstance(runs, list) and len(runs) > 0:
            print(f"First run type: {type(runs[0])}")

            # Debug the first run
            if isinstance(runs[0], dict):
                print(f"First run keys: {runs[0].keys()}")
                print(f"First run completed_at: {runs[0].get('completed_at')}")
                print(f"First run keystone_run_id: {runs[0].get('keystone_run_id')}")

                # Debug the dungeon information
                dungeon = runs[0].get("dungeon")
                if isinstance(dungeon, dict):
                    print(f"First run dungeon: {dungeon.get('name')}")
                else:
                    print(f"First run dungeon is not a dictionary: {type(dungeon)}")
                    if isinstance(dungeon, str):
                        print(f"First run dungeon (string): {dungeon}")

        # Handle different data formats
        if isinstance(runs, str):
            # If runs is a string, try to parse it as JSON
            try:
                import json
                runs = json.loads(runs)
                print("Converted runs string to JSON")
            except Exception as e:
                print(f"Error parsing runs as JSON: {e}")
                import traceback
                print(traceback.format_exc())
                return None

        if not isinstance(runs, list):
            print(f"Runs is not a list: {type(runs)}")
            return None

        if len(runs) == 0:
            print("Runs list is empty")
            return None

        # Check if all runs have the required fields
        valid_runs = []
        for i, run in enumerate(runs):
            if not isinstance(run, dict):
                print(f"Run {i} is not a dictionary: {type(run)}")
                continue

            if "completed_at" not in run:
                print(f"Run {i} is missing completed_at field")
                continue

            # Add the run to valid runs if it has completed_at
            # We'll use keystone_run_id if available, otherwise we'll generate a unique ID
            valid_runs.append(run)

        if not valid_runs:
            print("No valid runs found")
            return None

        print(f"Found {len(valid_runs)} valid runs")

        # Sort runs by completed_at timestamp (most recent first)
        try:
            print("Sorting runs by completed_at timestamp")
            sorted_runs = sorted(valid_runs, key=lambda x: x.get("completed_at", ""), reverse=True)

            if sorted_runs:
                latest_run = sorted_runs[0]

                # If the run doesn't have mythic_plus_id, add it using keystone_run_id or generate one
                if "mythic_plus_id" not in latest_run:
                    if "keystone_run_id" in latest_run:
                        latest_run["mythic_plus_id"] = latest_run["keystone_run_id"]
                        print(f"Using keystone_run_id as mythic_plus_id: {latest_run['mythic_plus_id']}")
                    else:
                        # Generate a unique ID based on dungeon, level, and completed_at
                        import hashlib
                        dungeon_name = latest_run.get("dungeon", "unknown")
                        if isinstance(dungeon_name, dict):
                            dungeon_name = dungeon_name.get("name", "unknown")

                        unique_string = f"{dungeon_name}_{latest_run.get('mythic_level', 0)}_{latest_run.get('completed_at', '')}"
                        unique_id = int(hashlib.md5(unique_string.encode()).hexdigest(), 16) % 10**10  # 10-digit number
                        latest_run["mythic_plus_id"] = unique_id
                        print(f"Generated unique ID as mythic_plus_id: {latest_run['mythic_plus_id']}")

                print(f"Latest run: {latest_run.get('mythic_plus_id')} completed at {latest_run.get('completed_at')}")
                return latest_run
            else:
                print("No runs after sorting")
                return None
        except Exception as e:
            print(f"Error sorting runs: {e}")
            import traceback
            print(traceback.format_exc())

            # If sorting fails, just return the first run if available
            if valid_runs:
                # Add mythic_plus_id if needed
                if "mythic_plus_id" not in valid_runs[0]:
                    if "keystone_run_id" in valid_runs[0]:
                        valid_runs[0]["mythic_plus_id"] = valid_runs[0]["keystone_run_id"]
                    else:
                        # Generate a unique ID
                        import hashlib
                        dungeon_name = valid_runs[0].get("dungeon", "unknown")
                        if isinstance(dungeon_name, dict):
                            dungeon_name = dungeon_name.get("name", "unknown")

                        unique_string = f"{dungeon_name}_{valid_runs[0].get('mythic_level', 0)}_{valid_runs[0].get('completed_at', '')}"
                        unique_id = int(hashlib.md5(unique_string.encode()).hexdigest(), 16) % 10**10  # 10-digit number
                        valid_runs[0]["mythic_plus_id"] = unique_id

                print(f"Returning first run as fallback: {valid_runs[0].get('mythic_plus_id')}")
                return valid_runs[0]
            else:
                print("No valid runs to return as fallback")
                return None
