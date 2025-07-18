import aiohttp
import asyncio
import json
import logging
import sys
import os
from datetime import datetime

import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('raiderio_dungeons')

# Get configuration values from config.py
API_ACCESS_KEY = config.API_ACCESS_KEY
CURRENT_EXPANSION = config.CURRENT_EXPANSION
CURRENT_SEASON = config.CURRENT_SEASON
CURRENT_SEASON_SHORT = config.CURRENT_SEASON_SHORT

# This is the single place to update when a new season starts
# Now these values are loaded from .env file through config.py

class DungeonCache:
    """Class to cache dungeon information from Raider.io API"""

    def __init__(self, cache_file="dungeon_cache.json"):
        """Initialize the dungeon cache"""
        self.cache_file = cache_file
        self.dungeons = {}
        self.last_updated = None
        self.current_season = None
        self.load_cache()

    def load_cache(self):
        """Load the dungeon cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    self.dungeons = cache_data.get("dungeons", {})
                    self.last_updated = cache_data.get("last_updated")
                    self.current_season = cache_data.get("current_season")
                    logger.info(f"Loaded dungeon cache from {self.cache_file}")
                    logger.info(f"Cache contains {len(self.dungeons)} dungeons")
                    logger.info(f"Last updated: {self.last_updated}")
                    logger.info(f"Current season: {self.current_season}")
        except Exception as e:
            logger.error(f"Error loading dungeon cache: {e}")

    def save_cache(self):
        """Save the dungeon cache to file"""
        try:
            cache_data = {
                "dungeons": self.dungeons,
                "last_updated": datetime.now().isoformat(),
                "current_season": self.current_season
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                logger.info(f"Saved dungeon cache to {self.cache_file}")
        except Exception as e:
            logger.error(f"Error saving dungeon cache: {e}")

    def update_dungeons(self, dungeons, season_slug):
        """Update the dungeon cache with new dungeons"""
        self.current_season = season_slug

        for dungeon in dungeons:
            name = dungeon.get("name")
            if name:
                self.dungeons[name] = {
                    "id": dungeon.get("id"),
                    "challenge_mode_id": dungeon.get("challenge_mode_id"),
                    "slug": dungeon.get("slug"),
                    "short_name": dungeon.get("short_name"),
                    "keystone_timer_seconds": dungeon.get("keystone_timer_seconds"),
                    "icon_url": dungeon.get("icon_url"),
                    "background_image_url": dungeon.get("background_image_url")
                }

        self.last_updated = datetime.now().isoformat()
        self.save_cache()

    def get_dungeon_banner(self, dungeon_name):
        """Get the banner URL for a dungeon"""
        dungeon = self.dungeons.get(dungeon_name)
        if dungeon and dungeon.get("background_image_url"):
            return dungeon.get("background_image_url")
        return None

    def get_dungeon_banners_dict(self):
        """Get a dictionary of dungeon names and banner URLs"""
        banners = {}
        for name, dungeon in self.dungeons.items():
            if dungeon.get("background_image_url"):
                banners[name] = dungeon.get("background_image_url")
        return banners

    def is_cache_valid(self, max_age_hours=24):
        """Check if the cache is still valid"""
        if not self.last_updated:
            return False

        try:
            last_updated = datetime.fromisoformat(self.last_updated)
            age = datetime.now() - last_updated
            return age.total_seconds() < max_age_hours * 3600
        except Exception:
            return False

    def force_refresh(self):
        """Force a refresh of the cache by invalidating the last_updated timestamp"""
        self.last_updated = None
        logger.info("Forced refresh of dungeon cache")

async def fetch_current_dungeons():
    """Fetch the current season dungeons from Raider.io API"""
    logger.info(f"Fetching dungeons for expansion {CURRENT_EXPANSION}...")

    async with aiohttp.ClientSession() as session:
        # Try to get the current season dungeons
        try:
            # Use the mythic-plus/static-data endpoint
            url = f"{config.RAIDERIO_API_URL}/mythic-plus/static-data"
            params = {
                "expansion_id": CURRENT_EXPANSION,
                "access_key": API_ACCESS_KEY
            }

            logger.info(f"Requesting: {url} with params {params}")
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Successfully fetched static data")

                    # Extract seasons
                    seasons = data.get("seasons", [])
                    current_season_data = None

                    # Find the current season
                    for season in seasons:
                        if season.get("slug") == CURRENT_SEASON:
                            current_season_data = season
                            break

                    if current_season_data:
                        logger.info(f"Found current season: {current_season_data.get('name')}")
                        dungeons = current_season_data.get("dungeons", [])

                        logger.info(f"Current season has {len(dungeons)} dungeons:")
                        for dungeon in dungeons:
                            logger.info(f"  - {dungeon.get('name')} (ID: {dungeon.get('id')})")

                        return dungeons, current_season_data.get("slug")
                    else:
                        logger.warning(f"Could not find current season {CURRENT_SEASON} in static data")

                        # Try to find any season with the short name
                        for season in seasons:
                            if season.get("short_name") == CURRENT_SEASON_SHORT:
                                logger.info(f"Found season by short name: {season.get('name')}")
                                dungeons = season.get("dungeons", [])

                                logger.info(f"Season has {len(dungeons)} dungeons:")
                                for dungeon in dungeons:
                                    logger.info(f"  - {dungeon.get('name')} (ID: {dungeon.get('id')})")

                                return dungeons, season.get("slug")

                        # If we still can't find the season, use the first one
                        if seasons:
                            logger.warning(f"Using first available season: {seasons[0].get('name')}")
                            dungeons = seasons[0].get("dungeons", [])

                            logger.info(f"Season has {len(dungeons)} dungeons:")
                            for dungeon in dungeons:
                                logger.info(f"  - {dungeon.get('name')} (ID: {dungeon.get('id')})")

                            return dungeons, seasons[0].get("slug")
                else:
                    response_text = await response.text()
                    logger.warning(f"Failed to fetch static data: {response.status}")
                    logger.warning(f"Response: {response_text}")
        except Exception as e:
            logger.error(f"Error fetching static data: {e}")
            import traceback
            logger.error(traceback.format_exc())

    logger.error("Failed to fetch current dungeons")
    return [], None

async def update_dungeon_cache():
    """Update the dungeon cache with current season dungeons"""
    # Initialize the dungeon cache
    cache = DungeonCache()

    # Check if the cache is still valid
    if cache.is_cache_valid():
        logger.info("Dungeon cache is still valid")
        return cache

    # Fetch current dungeons from Raider.io API
    dungeons, season_slug = await fetch_current_dungeons()

    if dungeons and season_slug:
        # Update the cache with new dungeons
        cache.update_dungeons(dungeons, season_slug)
        logger.info(f"Updated dungeon cache with {len(dungeons)} dungeons from season {season_slug}")
    else:
        logger.warning("Could not update dungeon cache")

    return cache

def get_dungeon_banner_url(dungeon_name):
    """Get the banner URL for a dungeon (synchronous wrapper)"""
    # Initialize the dungeon cache
    cache = DungeonCache()

    # Try to get the banner from the cache
    banner_url = cache.get_dungeon_banner(dungeon_name)

    if banner_url:
        return banner_url

    # If not found in cache, try to find a similar dungeon name
    for name, dungeon in cache.dungeons.items():
        # Check if the dungeon name contains our search term or vice versa
        if (dungeon_name.lower() in name.lower() or
            name.lower() in dungeon_name.lower()):
            if dungeon.get("background_image_url"):
                return dungeon.get("background_image_url")

    # If still not found, use a generic Raider.io dungeon image
    # This is not hardcoded - it's a generic Raider.io image for dungeons
    return "https://cdnassets.raider.io/images/fb_app_image.jpg"

async def main():
    """Main function"""
    try:
        # Update the dungeon cache
        cache = await update_dungeon_cache()

        # Get the dungeon banners dictionary
        banners = cache.get_dungeon_banners_dict()

        # Print the dictionary in a format that can be copied to utils.py
        logger.info("Dungeon banner dictionary:")
        logger.info("dungeon_banners = {")
        for name, url in banners.items():
            logger.info(f'    "{name}": "{url}",')
        logger.info("}")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
