# Mythic+ Tracker Discord Bot

A Discord bot that tracks World of Warcraft Mythic+ runs from Raider.io API and sends notifications when tracked players complete new runs. Supports multiple Discord servers with server-specific tracking and notifications.

## Features

- Track players' Mythic+ runs using the Raider.io API
- Multi-server support - track different players on different Discord servers
- Server-specific notification channels
- Web interface for easy configuration
- Persistent tracking even if the bot restarts
- Formatted notifications for completed runs with class-colored embeds
- Slash commands for easy interaction
- Channel restriction to keep bot activity in a designated channel

## Commands

- `/track <name> <realm> [region]` - Track a player's Mythic+ runs
- `/track_and_check <name> <realm> [region]` - Track a player and immediately check for runs
- `/untrack <name> <realm> [region]` - Stop tracking a player
- `/list` - List all tracked players in the current server
- `/check_runs <name> <realm> [region]` - Force check for new runs for a specific character
- `/check_all` - Force check for new runs for all tracked characters (admin only)
- `/set_channel #channel` - Set the channel for notifications (admin only)
- `/ping` - Check if the bot is responding

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a Discord bot on the [Discord Developer Portal](https://discord.com/developers/applications)
4. Enable the "Message Content" intent in the Bot settings
5. Copy your bot token
6. Create a `.env` file in the project root with the following content (all fields are required):
   ```
   # Discord Bot Token (required)
   DISCORD_TOKEN=your_discord_token_here

   # Check interval in seconds (required)
   CHECK_INTERVAL=60

   # Database file name (required)
   DATABASE_FILE=mythictracker.db

   # Raider.io API configuration (required)
   RAIDERIO_API_URL=https://raider.io/api/v1
   API_ACCESS_KEY=your_raiderio_api_key_here

   # Current expansion and season (required)
   CURRENT_EXPANSION=10
   CURRENT_SEASON=season-tww-2
   CURRENT_SEASON_SHORT=TWW2

   # Discord embed color (required)
   EMBED_COLOR=3447003

   # Web server configuration (required)
   WEB_HOST=0.0.0.0
   WEB_PORT=5000
   WEB_DEBUG=False

   # Discord OAuth2 client ID for bot invite link (required)
   CLIENT_ID=your_client_id_here

   # Flask secret key for session management (required)
   FLASK_SECRET_KEY=your_secret_key_here
   ```
   - All fields are required - the bot will not start if any are missing
   - Replace `your_discord_token_here` with your actual bot token
   - Replace `your_raiderio_api_key_here` with your Raider.io API key
   - Replace `your_client_id_here` with your Discord application client ID
   - Replace `your_secret_key_here` with a random string for Flask session security
   - To get a channel ID for server configuration, enable Developer Mode in Discord (Settings > Advanced), then right-click on a channel and select "Copy ID"
   - Each server must configure its own channel using the `/set_channel` command or the web interface
7. Run the bot:
   ```
   python main.py
   ```
8. Access the web interface at `http://your_server_ip:5000`

## Bot Invite Link

You can invite the bot to your server using the following link (replace `YOUR_CLIENT_ID` with your actual client ID):

```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=139586816000&integration_type=0&scope=bot
```

## Web Interface

The bot includes a web interface that allows server administrators to:

1. Invite the bot to their server
2. Configure the notification channel for their server

The web interface is accessible at `http://your_server_ip:5000` and includes:

- Landing page with bot information and invite link
- Setup page to configure the notification channel
- Help page with command documentation

## Multi-Server Support

The bot supports multiple Discord servers with the following features:

- Each server can track its own set of players
- Each server must have its own notification channel
- Notifications are only sent to the server where the player is being tracked
- Server administrators must set the notification channel using the `/set_channel` command or the web interface
- No commands will work until a channel is configured for the server

## How It Works

The bot checks the Raider.io API every minute for new Mythic+ runs completed by tracked players. When a new run is detected, it sends a formatted notification to the Discord server with details about the run, including:

- Dungeon name and level
- Completion time and whether it was timed
- Score earned
- Group members and their roles (tanks, healers, DPS)
- Links to the run and character profiles

The notification embeds are color-coded based on the character's class:
- Paladin: Pink
- Priest: White
- Mage: Blue
- Druid: Orange
- Warrior: Brown
- Evoker: Teal
- Monk: Lime green
- Demon Hunter: Purple
- Rogue: Yellow
- Death Knight: Red
- Shaman: Blue
- Hunter: Green
- Warlock: Light purple

## Requirements

- Python 3.8+
- discord.py 2.0+
- aiohttp
- Flask
- SQLite (included with Python)
