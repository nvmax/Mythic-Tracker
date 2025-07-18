# Discord Bot Configuration
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord Bot Token (required)
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN must be set in the .env file")

# Command prefix
PREFIX = "!"

# Check interval in seconds (required)
CHECK_INTERVAL_STR = os.getenv("CHECK_INTERVAL")
if not CHECK_INTERVAL_STR:
    raise ValueError("CHECK_INTERVAL must be set in the .env file")
CHECK_INTERVAL = int(CHECK_INTERVAL_STR)

# Database file name (required)
DATABASE_FILE = os.getenv("DATABASE_FILE")
if not DATABASE_FILE:
    raise ValueError("DATABASE_FILE must be set in the .env file")

# Raider.io API base URL (required)
RAIDERIO_API_URL = os.getenv("RAIDERIO_API_URL")
if not RAIDERIO_API_URL:
    raise ValueError("RAIDERIO_API_URL must be set in the .env file")

# Raider.io API access key (required)
API_ACCESS_KEY = os.getenv("API_ACCESS_KEY")
if not API_ACCESS_KEY:
    raise ValueError("API_ACCESS_KEY must be set in the .env file")

# Current expansion ID (required)
CURRENT_EXPANSION_STR = os.getenv("CURRENT_EXPANSION")
if not CURRENT_EXPANSION_STR:
    raise ValueError("CURRENT_EXPANSION must be set in the .env file")
CURRENT_EXPANSION = int(CURRENT_EXPANSION_STR)

# Current season information (required)
CURRENT_SEASON = os.getenv("CURRENT_SEASON")
if not CURRENT_SEASON:
    raise ValueError("CURRENT_SEASON must be set in the .env file")

CURRENT_SEASON_SHORT = os.getenv("CURRENT_SEASON_SHORT")
if not CURRENT_SEASON_SHORT:
    raise ValueError("CURRENT_SEASON_SHORT must be set in the .env file")

# Discord color for embeds (required)
EMBED_COLOR_STR = os.getenv("EMBED_COLOR")
if not EMBED_COLOR_STR:
    raise ValueError("EMBED_COLOR must be set in the .env file")
EMBED_COLOR = int(EMBED_COLOR_STR)

# Channel ID is no longer used
# Each server must set its own channel ID using /set_channel or the web interface
CHANNEL_ID = None

# Web server configuration (required)
WEB_HOST = os.getenv("WEB_HOST")
if not WEB_HOST:
    raise ValueError("WEB_HOST must be set in the .env file")

WEB_PORT_STR = os.getenv("WEB_PORT")
if not WEB_PORT_STR:
    raise ValueError("WEB_PORT must be set in the .env file")
WEB_PORT = int(WEB_PORT_STR)

WEB_DEBUG_STR = os.getenv("WEB_DEBUG")
if not WEB_DEBUG_STR:
    raise ValueError("WEB_DEBUG must be set in the .env file")
WEB_DEBUG = WEB_DEBUG_STR.lower() == "true"

# Bot client ID for OAuth2 URL (required)
CLIENT_ID = os.getenv("CLIENT_ID")
if not CLIENT_ID:
    raise ValueError("CLIENT_ID must be set in the .env file")

# Flask secret key (required)
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not FLASK_SECRET_KEY:
    raise ValueError("FLASK_SECRET_KEY must be set in the .env file")

# Bot invite URL
BOT_INVITE_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=139586816000&integration_type=0&scope=bot"
