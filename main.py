import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import logging
import sys
import os
import traceback
from datetime import datetime, timedelta

import config
from database import Database
from raiderio_api import RaiderIO
import utils

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('mythic_tracker')

# Initialize Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

# Initialize database
db = Database()

# Define a check to restrict commands to the specified channel
def is_in_allowed_channel():
    async def predicate(interaction: discord.Interaction):
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else None

        if not server_id:
            logger.warning("Command used outside of a server (DM)")
            await interaction.response.send_message(
                "This command can only be used in a server, not in DMs.",
                ephemeral=True
            )
            return False

        # Check if there's a server-specific channel configured
        server_channel_id = db.get_server_channel(server_id)

        # Server must have a channel configured
        if not server_channel_id:
            logger.info(f"No channel configured for server {server_id}")
            await interaction.response.send_message(
                "This server has not configured a channel for the bot. An administrator must use the `/set_channel` command or the web interface to set a channel.",
                ephemeral=True
            )
            return False

        allowed_channel_id = None

        # Try server-specific channel
        try:
            allowed_channel_id = int(server_channel_id)
            logger.info(f"Using server-specific channel ID: {allowed_channel_id}")
        except ValueError:
            logger.error(f"Invalid server-specific channel ID: {server_channel_id}")
            await interaction.response.send_message(
                f"The configured channel ID ({server_channel_id}) is invalid. An administrator must use the `/set_channel` command or the web interface to set a valid channel.",
                ephemeral=True
            )
            return False

        # If we have a valid channel ID, check if the command is used in that channel
        if allowed_channel_id:
            if interaction.channel_id == allowed_channel_id:
                return True
            else:
                # If not in the allowed channel, respond with an error message
                channel = interaction.client.get_channel(allowed_channel_id)
                channel_mention = f"<#{allowed_channel_id}>" if channel else f"the designated channel (ID: {allowed_channel_id})"
                await interaction.response.send_message(
                    f"This command can only be used in {channel_mention}.",
                    ephemeral=True
                )
                return False

        # If we get here, there's no valid channel ID
        return True

    return app_commands.check(predicate)

@bot.event
async def on_ready():
    """Event triggered when the bot is ready"""
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')

    # Log the configured channel
    if config.CHANNEL_ID:
        try:
            channel_id = int(config.CHANNEL_ID)
            channel = bot.get_channel(channel_id)
            if channel:
                logger.info(f"Bot restricted to channel: #{channel.name} ({channel_id})")
            else:
                logger.warning(f"Configured channel ID {channel_id} not found")
        except ValueError:
            logger.error(f"Invalid channel ID in config: {config.CHANNEL_ID}")
    else:
        logger.info("No channel restriction configured")

    # Initialize dungeon cache
    try:
        logger.info("Initializing dungeon cache...")
        from raiderio_dungeons import update_dungeon_cache
        cache = await update_dungeon_cache()
        logger.info(f"Dungeon cache initialized with {len(cache.dungeons)} dungeons")
        logger.info(f"Current season: {cache.current_season}")
    except Exception as e:
        logger.error(f"Error initializing dungeon cache: {e}")
        logger.error(traceback.format_exc())

    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
        for cmd in synced:
            logger.info(f"  - {cmd.name}: {cmd.description}")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        logger.error(traceback.format_exc())

    # Start the background task to check for new runs
    if not check_mythic_runs.is_running():
        check_mythic_runs.start()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    """Handle errors in application commands"""
    logger.error(f"Command error: {error}")
    logger.error(traceback.format_exc())

    # Send error message to user
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"An error occurred: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"An error occurred: {error}", ephemeral=True)
    except Exception as e:
        logger.error(f"Error sending error message: {e}")
        logger.error(traceback.format_exc())

@tasks.loop(seconds=config.CHECK_INTERVAL)
async def check_mythic_runs():
    """Background task to check for new mythic+ runs"""
    logger.info("Checking for new mythic+ runs...")

    # Get all tracked players
    players = db.get_all_players()
    if not players:
        logger.info("No players are being tracked")
        return

    logger.info(f"Found {len(players)} tracked players")

    async with RaiderIO() as rio:
        for player in players:
            try:
                logger.info(f"Checking runs for {player['name']}-{player['realm']} ({player['region']})")
                logger.info(f"Last run ID: {player['last_run_id']}, Last checked: {player['last_checked']}")

                # Get player's recent runs
                data = await rio.get_character_mythic_plus_runs(
                    player['name'],
                    player['realm'],
                    player['region']
                )

                if not data:
                    logger.warning(f"No data found for {player['name']}-{player['realm']}")
                    db.update_player_last_checked(player['id'])
                    continue

                logger.info(f"Data received for {player['name']}-{player['realm']}")

                # Debug the data
                if isinstance(data, dict):
                    logger.info(f"Data keys: {data.keys()}")
                    if "mythic_plus_recent_runs" in data:
                        logger.info(f"Found {len(data['mythic_plus_recent_runs'])} recent runs")
                    else:
                        logger.warning(f"No mythic_plus_recent_runs key in data")
                else:
                    logger.warning(f"Data is not a dictionary: {type(data)}")

                # Parse runs
                runs = rio.parse_mythic_plus_runs(data)
                if not runs:
                    logger.info(f"No recent runs found for {player['name']}-{player['realm']}")
                    db.update_player_last_checked(player['id'])
                    continue

                logger.info(f"Parsed {len(runs)} runs for {player['name']}-{player['realm']}")

                # Get the latest run
                latest_run = rio.get_latest_run(runs)
                if not latest_run:
                    logger.warning(f"Could not determine latest run for {player['name']}-{player['realm']}")
                    continue

                logger.info(f"Latest run for {player['name']}-{player['realm']}: {latest_run.get('mythic_plus_id', 0)}")

                # Get detailed run information
                try:
                    logger.info(f"Fetching detailed run information")
                    detailed_run = await rio.get_run_details(latest_run)
                    if detailed_run != latest_run:
                        logger.info(f"Got detailed run information")
                        latest_run = detailed_run
                except Exception as e:
                    logger.error(f"Error fetching detailed run information: {e}")
                    logger.error(traceback.format_exc())

                # Check if this is a new run and from Season 3
                run_id = latest_run.get("mythic_plus_id", 0)
                run_url = latest_run.get("url", "")

                # Only track Season 3 runs
                if 'season-tww-3' not in run_url:
                    logger.info(f"Skipping non-Season 3 run for {player['name']}-{player['realm']}: {run_id}")
                    db.update_player_last_checked(player['id'])
                    continue

                if run_id > player['last_run_id']:
                    logger.info(f"New run found for {player['name']}-{player['realm']}: {run_id} (previous: {player['last_run_id']})")

                    # Add run to database
                    dungeon_info = latest_run.get("dungeon", {})
                    if isinstance(dungeon_info, dict):
                        dungeon_name = dungeon_info.get("name", "Unknown")
                    elif isinstance(dungeon_info, str):
                        dungeon_name = dungeon_info
                    else:
                        dungeon_name = "Unknown"

                    mythic_level = latest_run.get("mythic_level", 0)
                    completed_at = latest_run.get("completed_at", "")
                    timed = latest_run.get("is_completed_within_time", False)
                    run_time_ms = latest_run.get("clear_time_ms", 0)
                    score = latest_run.get("score", 0)
                    url = latest_run.get("url", "")

                    logger.info(f"Run details: {dungeon_name} +{mythic_level}, Completed: {completed_at}, Timed: {timed}")

                    db.add_run(
                        player['id'], run_id, dungeon_name, mythic_level,
                        completed_at, timed, run_time_ms, score, url, latest_run
                    )
                    logger.info(f"Added run to database")

                    # Update player's last run ID
                    db.update_player_last_run(player['id'], run_id)
                    logger.info(f"Updated player's last run ID to {run_id}")

                    # Send notification to the server where the player is tracked
                    logger.info(f"Sending notification for new run")
                    await send_run_notification(latest_run, data, player['id'])
                    logger.info(f"Notification sent")
                else:
                    logger.info(f"No new runs for {player['name']}-{player['realm']} (latest: {run_id}, stored: {player['last_run_id']})")
                    # Just update the last checked timestamp
                    db.update_player_last_checked(player['id'])

            except Exception as e:
                logger.error(f"Error checking runs for {player['name']}-{player['realm']}: {e}")
                logger.error(traceback.format_exc())

@check_mythic_runs.before_loop
async def before_check_mythic_runs():
    """Wait until the bot is ready before starting the task"""
    await bot.wait_until_ready()

async def send_run_notification(run_data, character_data, player_id=None):
    """Send a notification about a new mythic+ run"""
    logger.info("Creating embed for run notification")

    # Debug the run data
    if isinstance(run_data, dict):
        logger.info(f"Run data keys: {run_data.keys()}")
        dungeon_info = run_data.get("dungeon", {})
        if isinstance(dungeon_info, dict):
            logger.info(f"Dungeon: {dungeon_info.get('name')}")
        else:
            logger.warning(f"Dungeon info is not a dictionary: {dungeon_info}")

        logger.info(f"Mythic level: {run_data.get('mythic_level')}")
        logger.info(f"Completed at: {run_data.get('completed_at')}")
        logger.info(f"Timed: {run_data.get('is_completed_within_time')}")
    else:
        logger.warning(f"Run data is not a dictionary: {type(run_data)}")

    # Get detailed run information
    try:
        async with RaiderIO() as rio:
            logger.info(f"Fetching detailed run information for notification")
            detailed_run = await rio.get_run_details(run_data)
            if detailed_run != run_data:
                logger.info(f"Got detailed run information for notification")
                run_data = detailed_run
    except Exception as e:
        logger.error(f"Error fetching detailed run information for notification: {e}")
        logger.error(traceback.format_exc())

    # Create the embed
    embed = utils.create_run_embed(run_data, character_data)
    if not embed:
        logger.error("Failed to create embed for run notification")
        return

    logger.info("Successfully created embed for run notification")

    # Get character information for logging
    character_name = character_data.get("name", "Unknown")
    character_realm = character_data.get("realm", "Unknown")
    character_region = character_data.get("region", "us")

    # If we have a player_id, get the server_id from the database
    if player_id:
        try:
            # Get the player record to find the server_id
            cursor = db.connection.cursor()
            cursor.execute('SELECT server_id FROM players WHERE id = ?', (player_id,))
            result = cursor.fetchone()

            if result:
                server_id = result['server_id']
                logger.info(f"Found server_id {server_id} for player_id {player_id}")

                # Get the channel ID for this server
                channel_id = db.get_server_channel(server_id)

                if channel_id:
                    logger.info(f"Using server-specific channel ID: {channel_id} for server {server_id}")
                    try:
                        # Get the channel by ID
                        channel_id = int(channel_id)
                        channel = bot.get_channel(channel_id)

                        if channel:
                            logger.info(f"Found channel: #{channel.name} ({channel_id}) in server {server_id}")
                            await channel.send(embed=embed)
                            logger.info(f"Sent run notification for {character_name}-{character_realm} to #{channel.name}")
                            return
                        else:
                            logger.error(f"Could not find channel with ID {channel_id} in server {server_id}")
                    except ValueError:
                        logger.error(f"Invalid channel ID: {channel_id} for server {server_id}")
                    except Exception as e:
                        logger.error(f"Error sending notification to channel {channel_id}: {e}")
                        logger.error(traceback.format_exc())
                else:
                    logger.info(f"No channel configured for server {server_id}, using fallback")
            else:
                logger.warning(f"Could not find server_id for player_id {player_id}")
        except Exception as e:
            logger.error(f"Error getting server_id for player_id {player_id}: {e}")
            logger.error(traceback.format_exc())

    # No fallback to global channel ID - each server must set its own channel
    logger.info("No server-specific channel configured for this server")

    # If we get here, we couldn't find a specific channel, so use the old behavior
    logger.info("No specific channel configured, sending to all guilds")
    for guild in bot.guilds:
        try:
            # If we have a player_id, check if this guild is the one where the player is tracked
            if player_id:
                cursor = db.connection.cursor()
                cursor.execute('SELECT server_id FROM players WHERE id = ?', (player_id,))
                result = cursor.fetchone()

                if result and result['server_id'] != str(guild.id):
                    logger.info(f"Skipping guild {guild.name} ({guild.id}) as it's not the server where the player is tracked")
                    continue

            logger.info(f"Sending notification to guild: {guild.name}")

            # Try to find a suitable channel to send the notification
            # Priority: channel named 'mythic-runs', then 'mythic', then 'general', then first text channel
            target_channel = None

            for channel_name in ['mythic-runs', 'mythic', 'general']:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    logger.info(f"Found preferred channel: #{channel.name}")
                    target_channel = channel
                    break

            # If no preferred channel found, use the first text channel
            if not target_channel and guild.text_channels:
                target_channel = guild.text_channels[0]
                logger.info(f"Using first available channel: #{target_channel.name}")

            if target_channel:
                await target_channel.send(embed=embed)
                logger.info(f"Sent run notification for {character_name}-{character_realm} to {guild.name} in #{target_channel.name}")
            else:
                logger.warning(f"No suitable channel found in guild {guild.name}")

        except Exception as e:
            logger.error(f"Error sending notification to guild {guild.name}: {e}")
            logger.error(traceback.format_exc())

@bot.tree.command(name="track_and_check", description="Track a player and immediately check for new runs")
@app_commands.describe(
    name="Character name",
    realm="Realm name",
    region="Region (us, eu, kr, tw, cn)"
)
@is_in_allowed_channel()
async def track_and_check_command(interaction: discord.Interaction, name: str, realm: str, region: str = "us"):
    """Command to track a player and immediately check for new runs"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else '0'

        logger.info(f"Track and check command used by {interaction.user} for {name}-{realm} ({region}) in server {server_id}")

        await interaction.response.defer(ephemeral=True)

        # Validate region
        valid_regions = ["us", "eu", "kr", "tw", "cn"]
        if region.lower() not in valid_regions:
            await interaction.followup.send(f"Invalid region. Please use one of: {', '.join(valid_regions)}")
            return

        # Check if player exists on Raider.io
        try:
            async with RaiderIO() as rio:
                logger.info(f"Fetching character profile for {name}-{realm} ({region})")
                data = await rio.get_character_profile(name, realm, region)

                if not data:
                    logger.warning(f"Character not found: {name}-{realm} ({region})")
                    await interaction.followup.send(f"Character not found: {name}-{realm} ({region}). Please check the spelling and try again.")
                    return

                # Add player to database with server ID
                logger.info(f"Adding player to database: {name}-{realm} ({region}) for server {server_id}")
                success = db.add_player(name, realm, region, server_id)

                if success:
                    logger.info(f"Successfully added player: {name}-{realm} ({region}) for server {server_id}")
                    await interaction.followup.send(f"Now tracking {name}-{realm} ({region}) for new mythic+ runs!")
                else:
                    logger.info(f"Player already being tracked: {name}-{realm} ({region}) for server {server_id}")
                    await interaction.followup.send(f"Already tracking {name}-{realm} ({region}).")

                # Get player from database to get the ID
                player = db.get_player_by_name_realm(name, realm, region, server_id)
                if not player:
                    logger.error(f"Could not find player in database after adding: {name}-{realm} ({region}) for server {server_id}")
                    await interaction.followup.send(f"Error: Could not find player in database after adding.")
                    return

                # Parse runs
                logger.info(f"Parsing runs for {name}-{realm}")
                runs = rio.parse_mythic_plus_runs(data)
                if not runs:
                    logger.info(f"No recent runs found for {name}-{realm}")
                    await interaction.followup.send(f"No recent runs found for {name}-{realm}.")
                    return

                # Get the latest run
                latest_run = rio.get_latest_run(runs)
                if not latest_run:
                    logger.warning(f"Could not determine latest run for {name}-{realm}")
                    await interaction.followup.send(f"Could not determine the latest run for {name}-{realm}.")
                    return

                # Get detailed run information
                try:
                    logger.info(f"Fetching detailed run information")
                    detailed_run = await rio.get_run_details(latest_run)
                    if detailed_run != latest_run:
                        logger.info(f"Got detailed run information")
                        latest_run = detailed_run
                except Exception as e:
                    logger.error(f"Error fetching detailed run information: {e}")
                    logger.error(traceback.format_exc())

                # Create embed with run information
                embed = utils.create_run_embed(latest_run, data)
                if not embed:
                    logger.error(f"Error creating embed for the run")
                    await interaction.followup.send(f"Error creating embed for the run.")
                    return

                # Get run ID
                run_id = latest_run.get("mythic_plus_id", 0)

                # If the run doesn't have a mythic_plus_id, add it
                if run_id == 0 and "keystone_run_id" in latest_run:
                    run_id = latest_run["keystone_run_id"]
                    latest_run["mythic_plus_id"] = run_id
                    logger.info(f"Using keystone_run_id as mythic_plus_id: {run_id}")

                # Update player's last run ID
                db.update_player_last_run(player['id'], run_id)
                logger.info(f"Updated player's last run ID to {run_id}")

                # Add information about the run
                embed.add_field(name="Status", value="✅ This is the latest run. You will be notified of any new runs.", inline=False)

                # Send the embed to the user
                await interaction.followup.send(embed=embed, ephemeral=True)

                # Send notification to the server where the player is tracked
                await send_run_notification(latest_run, data, player['id'])

        except Exception as e:
            logger.error(f"Error in Raider.io API call: {e}")
            logger.error(traceback.format_exc())
            await interaction.followup.send(f"Error checking character on Raider.io: {e}")
    except Exception as e:
        logger.error(f"Error in track_and_check command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="track", description="Track a player's mythic+ runs")
@app_commands.describe(
    name="Character name",
    realm="Realm name",
    region="Region (us, eu, kr, tw, cn)"
)
@is_in_allowed_channel()
async def track_command(interaction: discord.Interaction, name: str, realm: str, region: str = "us"):
    """Command to track a player's mythic+ runs"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else '0'

        logger.info(f"Track command used by {interaction.user} for {name}-{realm} ({region}) in server {server_id}")

        await interaction.response.defer(ephemeral=True)

        # Validate region
        valid_regions = ["us", "eu", "kr", "tw", "cn"]
        if region.lower() not in valid_regions:
            await interaction.followup.send(f"Invalid region. Please use one of: {', '.join(valid_regions)}")
            return

        # Check if player exists on Raider.io
        try:
            async with RaiderIO() as rio:
                logger.info(f"Fetching character profile for {name}-{realm} ({region})")
                data = await rio.get_character_profile(name, realm, region)

                if not data:
                    logger.warning(f"Character not found: {name}-{realm} ({region})")
                    await interaction.followup.send(f"Character not found: {name}-{realm} ({region}). Please check the spelling and try again.")
                    return

                # Add player to database with server ID
                logger.info(f"Adding player to database: {name}-{realm} ({region}) for server {server_id}")
                success = db.add_player(name, realm, region, server_id)

                if success:
                    logger.info(f"Successfully added player: {name}-{realm} ({region}) for server {server_id}")

                    # Get player from database to get the ID
                    player = db.get_player_by_name_realm(name, realm, region, server_id)

                    if player:
                        # Get recent runs to set the last run ID
                        logger.info(f"Parsing runs for {name}-{realm}")
                        runs = rio.parse_mythic_plus_runs(data)
                        if runs:
                            latest_run = rio.get_latest_run(runs)
                            if latest_run:
                                run_id = latest_run.get("mythic_plus_id", 0)
                                logger.info(f"Setting last run ID to {run_id} for {name}-{realm}")
                                db.update_player_last_run(player['id'], run_id)

                    await interaction.followup.send(f"Now tracking {name}-{realm} ({region}) for new mythic+ runs!")
                else:
                    logger.info(f"Player already being tracked: {name}-{realm} ({region}) for server {server_id}")
                    await interaction.followup.send(f"Already tracking {name}-{realm} ({region}).")
        except Exception as e:
            logger.error(f"Error in Raider.io API call: {e}")
            logger.error(traceback.format_exc())
            await interaction.followup.send(f"Error checking character on Raider.io: {e}")
    except Exception as e:
        logger.error(f"Error in track command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="untrack", description="Stop tracking a player's mythic+ runs")
@app_commands.describe(
    name="Character name",
    realm="Realm name",
    region="Region (us, eu, kr, tw, cn)"
)
@is_in_allowed_channel()
async def untrack_command(interaction: discord.Interaction, name: str, realm: str, region: str = "us"):
    """Command to stop tracking a player's mythic+ runs"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else '0'

        logger.info(f"Untrack command used by {interaction.user} for {name}-{realm} ({region}) in server {server_id}")

        await interaction.response.defer(ephemeral=True)

        # Remove player from database with server ID
        logger.info(f"Removing player from database: {name}-{realm} ({region}) for server {server_id}")
        success = db.remove_player(name, realm, region, server_id)

        if success:
            logger.info(f"Successfully removed player: {name}-{realm} ({region}) from server {server_id}")
            await interaction.followup.send(f"Stopped tracking {name}-{realm} ({region}).")
        else:
            logger.info(f"Player not found for removal: {name}-{realm} ({region}) in server {server_id}")
            await interaction.followup.send(f"Not tracking {name}-{realm} ({region}).")
    except Exception as e:
        logger.error(f"Error in untrack command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="list", description="List all tracked players in this server")
@is_in_allowed_channel()
async def list_command(interaction: discord.Interaction):
    """Command to list all tracked players in the current server"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else '0'

        logger.info(f"List command used by {interaction.user} in server {server_id}")

        await interaction.response.defer(ephemeral=True)

        # Get tracked players for this server
        logger.info(f"Fetching tracked players for server {server_id} from database")
        players = db.get_players_by_server(server_id)

        if not players:
            logger.info(f"No players are being tracked in server {server_id}")
            await interaction.followup.send("No players are being tracked in this server.")
            return

        logger.info(f"Found {len(players)} tracked players in server {server_id}")

        # Create embed
        embed = discord.Embed(
            title="Tracked Players",
            description="List of players being tracked for mythic+ runs in this server",
            color=discord.Color(config.EMBED_COLOR)
        )

        # Add players to embed
        for player in players:
            name = player['name'].capitalize()
            realm = player['realm'].capitalize()
            region = player['region'].upper()

            embed.add_field(
                name=f"{name}-{realm} ({region})",
                value=f"Last checked: {player['last_checked']}",
                inline=False
            )

        await interaction.followup.send(embed=embed)
        logger.info("Successfully sent list of tracked players")
    except Exception as e:
        logger.error(f"Error in list command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="ping", description="Check if the bot is responding")
async def ping_command(interaction: discord.Interaction):
    """Simple command to check if the bot is responding"""
    try:
        logger.info(f"Ping command used by {interaction.user}")
        await interaction.response.send_message("Pong! The bot is working.", ephemeral=True)
        logger.info("Successfully responded to ping command")
    except Exception as e:
        logger.error(f"Error in ping command: {e}")
        logger.error(traceback.format_exc())

@bot.tree.command(name="set_channel", description="Set the channel for mythic+ run notifications")
@app_commands.describe(
    channel="The channel to use for notifications (mention the channel with #)"
)
@app_commands.default_permissions(administrator=True)
async def set_channel_command(interaction: discord.Interaction, channel: discord.TextChannel):
    """Command to set the channel for mythic+ run notifications"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else None

        if not server_id:
            await interaction.response.send_message("This command can only be used in a server, not in DMs.", ephemeral=True)
            return

        logger.info(f"Set channel command used by {interaction.user} in server {server_id} for channel {channel.name} ({channel.id})")

        await interaction.response.defer(ephemeral=True)

        # Set the channel in the database
        success = db.set_server_channel(server_id, str(channel.id))

        if success:
            logger.info(f"Successfully set channel for server {server_id} to {channel.name} ({channel.id})")
            await interaction.followup.send(f"Successfully set {channel.mention} as the channel for mythic+ run notifications in this server.", ephemeral=True)
        else:
            logger.error(f"Failed to set channel for server {server_id}")
            await interaction.followup.send("Failed to set the channel. Please try again later.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in set_channel command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="refresh_dungeons", description="Refresh the dungeon cache from Raider.io API")
@app_commands.default_permissions(administrator=True)
@is_in_allowed_channel()
async def refresh_dungeons_command(interaction: discord.Interaction):
    """Command to refresh the dungeon cache from Raider.io API"""
    try:
        logger.info(f"Refresh dungeons command used by {interaction.user}")

        await interaction.response.defer(ephemeral=True)

        # Force refresh the dungeon cache
        try:
            from raiderio_dungeons import DungeonCache, update_dungeon_cache, CURRENT_SEASON

            # Force refresh by invalidating the cache
            cache = DungeonCache()
            cache.force_refresh()

            # Update the cache with fresh data
            cache = await update_dungeon_cache()

            # Get the list of dungeons
            dungeons = list(cache.dungeons.keys())

            # Create embed with dungeon information
            embed = discord.Embed(
                title="Dungeon Cache Refreshed",
                description=f"Successfully refreshed the dungeon cache for {CURRENT_SEASON}",
                color=discord.Color(config.EMBED_COLOR)
            )

            # Add dungeon list to embed
            dungeon_list = "\n".join([f"• {dungeon}" for dungeon in dungeons])
            embed.add_field(name="Current Dungeons", value=dungeon_list, inline=False)

            # Add timestamp
            embed.set_footer(text=f"Last updated: {cache.last_updated}")

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Successfully refreshed dungeon cache with {len(dungeons)} dungeons")
        except Exception as e:
            logger.error(f"Error refreshing dungeon cache: {e}")
            logger.error(traceback.format_exc())
            await interaction.followup.send(f"Error refreshing dungeon cache: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in refresh_dungeons command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="check_all", description="Force check for new runs for all tracked characters")
@app_commands.default_permissions(administrator=True)
@is_in_allowed_channel()
async def check_all_command(interaction: discord.Interaction):
    """Command to force check for new runs for all tracked characters"""
    try:
        logger.info(f"Check all command used by {interaction.user}")

        await interaction.response.defer(ephemeral=True)

        # Get all tracked players
        players = db.get_all_players()
        if not players:
            await interaction.followup.send("No players are being tracked.")
            return

        await interaction.followup.send(f"Checking for new runs for {len(players)} tracked players...", ephemeral=True)

        # Run the background task manually
        await check_mythic_runs()

        await interaction.followup.send(f"Finished checking for new runs for all tracked players.", ephemeral=True)

    except Exception as e:
        logger.error(f"Error in check_all command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

@bot.tree.command(name="check_runs", description="Force check for new runs for a specific character")
@app_commands.describe(
    name="Character name",
    realm="Realm name",
    region="Region (us, eu, kr, tw, cn)"
)
@is_in_allowed_channel()
async def check_runs_command(interaction: discord.Interaction, name: str, realm: str, region: str = "us"):
    """Command to force check for new runs for a specific character"""
    try:
        # Get the server ID from the interaction
        server_id = str(interaction.guild_id) if interaction.guild_id else '0'

        logger.info(f"Check runs command used by {interaction.user} for {name}-{realm} ({region}) in server {server_id}")

        await interaction.response.defer(ephemeral=True)

        # Check if the player is being tracked in this server
        player = db.get_player_by_name_realm(name, realm, region, server_id)
        if not player:
            await interaction.followup.send(f"Not tracking {name}-{realm} ({region}) in this server. Use /track to start tracking this character.")
            return

        # Get player's recent runs
        async with RaiderIO() as rio:
            logger.info(f"Fetching runs for {name}-{realm} ({region})")
            data = await rio.get_character_mythic_plus_runs(name, realm, region)

            if not data:
                logger.warning(f"No data found for {name}-{realm} ({region})")
                await interaction.followup.send(f"No data found for {name}-{realm} ({region}). The character might not exist or has no recent runs.")
                return

            # Parse runs
            runs = rio.parse_mythic_plus_runs(data)
            if not runs:
                logger.info(f"No recent runs found for {name}-{realm} ({region})")
                await interaction.followup.send(f"No recent runs found for {name}-{realm} ({region}).")
                return

            # Get the latest run
            latest_run = rio.get_latest_run(runs)
            if not latest_run:
                await interaction.followup.send(f"Could not determine the latest run for {name}-{realm} ({region}).")
                return

            # Get detailed run information
            try:
                logger.info(f"Fetching detailed run information")
                detailed_run = await rio.get_run_details(latest_run)
                if detailed_run != latest_run:
                    logger.info(f"Got detailed run information")
                    latest_run = detailed_run
            except Exception as e:
                logger.error(f"Error fetching detailed run information: {e}")
                logger.error(traceback.format_exc())

            # Check if this is a new run
            run_id = latest_run.get("mythic_plus_id", 0)

            # Create embed with run information
            embed = utils.create_run_embed(latest_run, data)
            if not embed:
                await interaction.followup.send(f"Error creating embed for the run.")
                return

            # Add information about whether this is a new run
            if run_id > player['last_run_id']:
                logger.info(f"New run found for {name}-{realm} ({region}): {run_id}")
                embed.add_field(name="Status", value="✅ This is a new run! Updating database...", inline=False)

                # Add run to database
                dungeon_info = latest_run.get("dungeon", {})
                if isinstance(dungeon_info, dict):
                    dungeon_name = dungeon_info.get("name", "Unknown")
                elif isinstance(dungeon_info, str):
                    dungeon_name = dungeon_info
                else:
                    dungeon_name = "Unknown"

                mythic_level = latest_run.get("mythic_level", 0)
                completed_at = latest_run.get("completed_at", "")
                timed = latest_run.get("is_completed_within_time", False)
                run_time_ms = latest_run.get("clear_time_ms", 0)
                score = latest_run.get("score", 0)
                url = latest_run.get("url", "")

                db.add_run(
                    player['id'], run_id, dungeon_name, mythic_level,
                    completed_at, timed, run_time_ms, score, url, latest_run
                )

                # Update player's last run ID
                db.update_player_last_run(player['id'], run_id)

                # Send notification to the server where the player is tracked
                await send_run_notification(latest_run, data, player['id'])
            else:
                logger.info(f"Run already tracked for {name}-{realm} ({region}): {run_id}")
                embed.add_field(name="Status", value="ℹ️ This run is already tracked in the database.", inline=False)

                # Just update the last checked timestamp
                db.update_player_last_checked(player['id'])

            # Send the embed to the user
            await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in check_runs command: {e}")
        logger.error(traceback.format_exc())

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
        except Exception as follow_up_error:
            logger.error(f"Error sending error message: {follow_up_error}")

def run_discord_bot():
    """Run the Discord bot"""
    try:
        logger.info("Starting Discord bot...")
        bot.run(config.TOKEN)
    except Exception as e:
        logger.error(f"Error running Discord bot: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Close database connection
        logger.info("Closing database connection...")
        db.close()

def main():
    """Main function to run both the Discord bot and web server"""
    import threading
    import web_server

    # Start the web server in a separate thread
    web_thread = threading.Thread(target=web_server.run_web_server)
    web_thread.daemon = True  # This ensures the thread will exit when the main program exits
    web_thread.start()
    logger.info("Web server thread started")

    # Run the Discord bot in the main thread
    run_discord_bot()

if __name__ == "__main__":
    main()
