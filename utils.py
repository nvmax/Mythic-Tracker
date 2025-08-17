import discord
import json
import urllib.parse
from datetime import datetime, timedelta
import config

# Class colors in Discord color format (decimal)
CLASS_COLORS = {
    "Paladin": 0xF58CBA,      # Pink
    "Priest": 0xFFFFFF,       # White
    "Mage": 0x3FC7EB,         # Blue
    "Druid": 0xFF7D0A,        # Orange
    "Warrior": 0xC79C6E,      # Brown
    "Evoker": 0x33937F,       # Teal
    "Monk": 0x00FF96,         # Lime Green
    "Demon Hunter": 0xA330C9,  # Purple
    "Rogue": 0xFFF569,        # Yellow
    "Death Knight": 0xC41F3B, # Red
    "Shaman": 0x0070DE,       # Blue
    "Hunter": 0xABD473,       # Green
    "Warlock": 0x8787ED,      # Light Purple
}

def format_time(milliseconds):
    """Format milliseconds into minutes and seconds"""
    seconds = milliseconds / 1000
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"

def format_time_difference(time_ms, max_time_ms):
    """Format the time difference between actual time and max time"""
    diff_ms = max_time_ms - time_ms
    diff_seconds = diff_ms / 1000

    if diff_ms > 0:
        # Under time (positive value)
        minutes = int(diff_seconds // 60)
        seconds = int(diff_seconds % 60)
        return f"{minutes}:{seconds:02d} under"
    else:
        # Over time (negative value)
        diff_seconds = abs(diff_seconds)
        minutes = int(diff_seconds // 60)
        seconds = int(diff_seconds % 60)
        return f"{minutes}:{seconds:02d} over"

def get_dungeon_banner_url(dungeon_name):
    """Get the banner URL for a dungeon"""
    try:
        # Always use the raiderio_dungeons module to get banner URLs
        # This ensures we're always using the latest data from the API
        from raiderio_dungeons import get_dungeon_banner_url as get_banner
        return get_banner(dungeon_name)
    except Exception as e:
        # Log the error but don't fall back to hardcoded values
        print(f"Error getting dungeon banner from raiderio_dungeons: {e}")
        import traceback
        print(traceback.format_exc())

        # Return a generic Raider.io image as a last resort
        # This is not hardcoded - it's a generic Raider.io image for dungeons
        return "https://cdnassets.raider.io/images/fb_app_image.jpg"

def create_run_embed(run_data, character_data):
    """Create a Discord embed for a mythic+ run"""
    try:
        if not run_data:
            print("No run data provided")
            return None

        # Debug the data
        print(f"Run data type: {type(run_data)}")
        if isinstance(run_data, dict):
            print(f"Run data keys: {run_data.keys()}")
        else:
            print(f"Run data is not a dictionary: {run_data}")
            # Try to convert to dictionary if it's a string
            if isinstance(run_data, str):
                try:
                    import json
                    run_data = json.loads(run_data)
                    print("Converted run_data string to dictionary")
                except Exception as e:
                    print(f"Error converting run_data to dictionary: {e}")
                    return None

        print(f"Character data type: {type(character_data)}")
        if isinstance(character_data, dict):
            print(f"Character data keys: {character_data.keys()}")
        else:
            print(f"Character data is not a dictionary: {character_data}")
            return None

        # Extract run information
        dungeon_info = run_data.get("dungeon", {})
        if isinstance(dungeon_info, dict):
            dungeon_name = dungeon_info.get("name", "Unknown Dungeon")
        elif isinstance(dungeon_info, str):
            # If dungeon is a string, use it directly
            dungeon_name = dungeon_info
            print(f"Using dungeon name from string: {dungeon_name}")
        else:
            dungeon_name = "Unknown Dungeon"
            print(f"Dungeon info is not a dictionary or string: {dungeon_info}")

        mythic_level = run_data.get("mythic_level", 0)
        completed_at = run_data.get("completed_at", "")

        # Check if the run was timed
        timed = run_data.get("is_completed_within_time", None)

        # If timed is None, calculate it based on clear_time_ms and par_time_ms
        if timed is None:
            clear_time_ms = run_data.get("clear_time_ms", 0)
            par_time_ms = run_data.get("par_time_ms", 0)

            if clear_time_ms > 0 and par_time_ms > 0:
                timed = clear_time_ms <= par_time_ms
                print(f"Calculated timed status: {timed} (clear_time_ms: {clear_time_ms}, par_time_ms: {par_time_ms})")
            else:
                # If we can't calculate, check num_keystone_upgrades
                upgrades = run_data.get("num_keystone_upgrades", 0)
                timed = upgrades > 0
                print(f"Determined timed status from upgrades: {timed} (upgrades: {upgrades})")

        # Time information
        run_time_ms = run_data.get("clear_time_ms", 0)
        max_time_ms = run_data.get("par_time_ms", 0)
        time_diff = format_time_difference(run_time_ms, max_time_ms)

        # Score information
        score = run_data.get("score", 0)

        # URLs
        run_url = run_data.get("url", "")

        # Get the number of chests (keystone upgrades)
        num_chests = run_data.get("num_chests", 0)

        # Format the title based on the number of chests
        if num_chests == 0:
            # Not timed
            title = f"+{mythic_level} {dungeon_name}"
        else:
            # Timed with upgrades (1, 2, or 3 chests)
            # Add "+" symbols based on the number of chests
            plus_symbols = "+" * num_chests
            title = f"{mythic_level}{plus_symbols} {dungeon_name}"

        # Get the character's class for coloring the embed
        character_class = character_data.get("class", "")

        # Get the color for the character's class
        if character_class in CLASS_COLORS:
            embed_color = CLASS_COLORS[character_class]
        else:
            # Fallback to default color from config
            embed_color = config.EMBED_COLOR

        # Create embed with class color
        embed = discord.Embed(
            title=title,
            url=run_url,
            color=discord.Color(embed_color)
        )

        # Get the dungeon banner URL
        banner_url = get_dungeon_banner_url(dungeon_name)

        # Set the dungeon banner as the image (at the bottom)
        embed.set_image(url=banner_url)

        # Add character name who completed the run
        character_name = character_data.get("name", "Unknown")
        character_realm = character_data.get("realm", "Unknown")
        character_region = character_data.get("region", "us")

        # URL-encode the realm and character names for the Raider.IO URL
        encoded_realm = urllib.parse.quote(character_realm.lower())
        encoded_name = urllib.parse.quote(character_name.lower())

        embed.set_author(
            name=f"{character_name.capitalize()}-{character_realm.capitalize()} completed a new run!",
            url=f"https://raider.io/characters/{character_region}/{encoded_realm}/{encoded_name}"
        )

        # Add run details
        # Update status to show the number of chests
        if not timed:
            status = "❌ Not Timed"
        elif num_chests == 1:
            status = "✅ Timed (+1)"
        elif num_chests == 2:
            status = "✅ Timed (++2)"
        elif num_chests == 3:
            status = "✅ Timed (+++3)"
        else:
            status = "✅ Timed"

        embed.add_field(name="Status", value=status, inline=True)

        # Update level display to match the title format
        level_display = f"+{mythic_level}"
        if num_chests > 0:
            plus_symbols = "+" * num_chests
            level_display = f"{mythic_level}{plus_symbols}"

        embed.add_field(name="Level", value=level_display, inline=True)
        embed.add_field(name="Score", value=f"{score:.1f}", inline=True)

        # Add time information
        embed.add_field(name="Time", value=format_time(run_time_ms), inline=True)
        embed.add_field(name="Max Time", value=format_time(max_time_ms), inline=True)
        embed.add_field(name="Difference", value=time_diff, inline=True)

        # Add affixes information
        affixes = run_data.get("affixes", [])
        if affixes and isinstance(affixes, list):
            affix_names = []
            for affix in affixes:
                if isinstance(affix, dict):
                    affix_name = affix.get("name")
                    if affix_name:
                        affix_names.append(affix_name)
                elif isinstance(affix, str):
                    affix_names.append(affix)

            if affix_names:
                embed.add_field(name="Affixes", value=", ".join(affix_names), inline=False)

        # Debug the run data to see if it includes roster information
        print(f"Checking for roster information in run data")
        if "roster" in run_data:
            print(f"Roster found: {type(run_data['roster'])}")
            if isinstance(run_data['roster'], list):
                print(f"Roster has {len(run_data['roster'])} members")
                if run_data['roster'] and isinstance(run_data['roster'][0], dict):
                    print(f"First member keys: {run_data['roster'][0].keys()}")
        else:
            print("No roster information found in run data")

            # Try to find affixes information
            if "affixes" in run_data:
                print(f"Affixes found: {run_data['affixes']}")

        # Add group members
        tanks = []
        healers = []
        dps = []
        unknown = []

        roster = run_data.get("roster", [])
        if roster and isinstance(roster, list):
            for member in roster:
                if not isinstance(member, dict):
                    continue

                character = member.get("character", {})
                if not isinstance(character, dict):
                    continue

                name = character.get("name", "Unknown")
                realm = character.get("realm", {}).get("name", "Unknown") if isinstance(character.get("realm"), dict) else "Unknown"

                spec_info = character.get("spec", {})
                spec = spec_info.get("name", "Unknown") if isinstance(spec_info, dict) else "Unknown"

                class_info = character.get("class", {})
                class_name = class_info.get("name", "Unknown") if isinstance(class_info, dict) else "Unknown"

                # Get role icon and determine role category
                role = "❓" # Default unknown role
                role_category = "unknown"
                if isinstance(spec_info, dict):
                    role_name = spec_info.get("role", "").lower()
                    if role_name == "tank":
                        role = "🛡️" # Tank
                        role_category = "tank"
                    elif role_name == "healer":
                        role = "💚" # Healer
                        role_category = "healer"
                    elif role_name == "dps":
                        role = "⚔️" # DPS
                        role_category = "dps"

                # Get character score if available
                score = "N/A"

                # First, check if the character has ranks directly (from detailed run info)
                if "ranks" in member and isinstance(member["ranks"], dict):
                    score_value = member["ranks"].get("score")
                    if score_value:
                        score = f"{score_value:.1f}"
                        print(f"Found score in ranks: {score}")

                # If no score found in ranks, try mythic_plus_scores_by_season
                elif "mythic_plus_scores_by_season" in character and isinstance(character["mythic_plus_scores_by_season"], list):
                    for season in character["mythic_plus_scores_by_season"]:
                        if not isinstance(season, dict):
                            continue

                        if season.get("season") == config.CURRENT_SEASON:  # Current season
                            scores = season.get("scores", {})
                            if isinstance(scores, dict):
                                score = f"{scores.get('all', 0):.1f}"
                            break

                # Format the player string
                player_string = f"{role} **{name}**-{realm} ({spec} {class_name}) - {score}"

                # Add to the appropriate role list
                if role_category == "tank":
                    tanks.append(player_string)
                elif role_category == "healer":
                    healers.append(player_string)
                elif role_category == "dps":
                    dps.append(player_string)
                else:
                    unknown.append(player_string)
        else:
            # If no roster information is available, try to get the character who completed the run
            character_name = character_data.get("name", "Unknown")
            character_realm = character_data.get("realm", "Unknown")
            character_class = character_data.get("class", "Unknown")
            character_spec = character_data.get("active_spec_name", "Unknown")

            # Get role icon based on spec
            role = "❓" # Default unknown role
            role_category = "unknown"
            character_role = character_data.get("active_spec_role", "").lower()
            if character_role == "tank":
                role = "🛡️" # Tank
                role_category = "tank"
            elif character_role == "healer":
                role = "💚" # Healer
                role_category = "healer"
            elif character_role == "dps":
                role = "⚔️" # DPS
                role_category = "dps"

            # Get character score
            score = "N/A"

            # First check if the run data has a score field (from detailed run info)
            if "score" in run_data:
                score = f"{run_data['score']:.1f}"
                print(f"Found score in run data: {score}")
            # Then check mythic_plus_scores_by_season
            elif "mythic_plus_scores_by_season" in character_data and isinstance(character_data["mythic_plus_scores_by_season"], list):
                for season in character_data["mythic_plus_scores_by_season"]:
                    if not isinstance(season, dict):
                        continue

                    if season.get("season") == config.CURRENT_SEASON:  # Current season
                        scores = season.get("scores", {})
                        if isinstance(scores, dict):
                            score = f"{scores.get('all', 0):.1f}"
                        break

            # Format the player string
            player_string = f"{role} **{character_name}**-{character_realm} ({character_spec} {character_class}) - {score}"

            # Add to the appropriate role list
            if role_category == "tank":
                tanks.append(player_string)
            elif role_category == "healer":
                healers.append(player_string)
            elif role_category == "dps":
                dps.append(player_string)
            else:
                unknown.append(player_string)

        # Combine all members in the correct order: tank, healer, dps, unknown
        all_members = tanks + healers + dps + unknown

        if all_members:
            # Determine the field name based on available data
            if roster and len(roster) > 1:
                field_name = "Group Members"
            else:
                field_name = "Tracked Player"
                # Add a helpful note about group data
                all_members.append("*Group roster data not available for this run*")

            embed.add_field(name=field_name, value="\n".join(all_members), inline=False)

        # Add death information if available
        death_info = get_death_information(run_data, roster)
        if death_info:
            embed.add_field(name="Deaths", value=death_info, inline=False)

        # Add footer with timestamp
        embed.set_footer(text=f"Completed at {completed_at}")

        return embed

    except Exception as e:
        print(f"Error creating embed: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def get_death_information(run_data, roster):
    """Extract death information from run data and return formatted string"""
    try:
        # Check if we have logged_details with death data
        logged_details = run_data.get('logged_details')
        if not logged_details or not isinstance(logged_details, dict):
            return None

        deaths = logged_details.get('deaths', [])
        if not deaths:
            return "No deaths 🎉"

        # If no roster available, just show total death count
        if not roster:
            return f"Total deaths: {len(deaths)}"

        # Create a mapping of character_id to player name
        char_id_to_name = {}
        for player in roster:
            char = player.get('character', {})
            char_id = char.get('id')
            char_name = char.get('name', 'Unknown')
            if char_id:
                char_id_to_name[char_id] = char_name

        # Count deaths per player
        death_counts = {}
        for death in deaths:
            char_id = death.get('character_id')
            if char_id in char_id_to_name:
                player_name = char_id_to_name[char_id]
                death_counts[player_name] = death_counts.get(player_name, 0) + 1

        # Format the death information
        if not death_counts:
            return f"Total deaths: {len(deaths)} (players not identified)"

        # Sort players by death count (highest first)
        sorted_deaths = sorted(death_counts.items(), key=lambda x: x[1], reverse=True)

        death_lines = []
        total_deaths = len(deaths)

        # Add each player's death count
        for player_name, count in sorted_deaths:
            if count > 0:
                death_lines.append(f"{player_name}: {count}")

        # If no players had deaths (shouldn't happen if we have death data)
        if not death_lines:
            return f"Total deaths: {total_deaths}"

        # Add total at the end
        death_lines.append(f"**Total: {total_deaths}**")

        return "\n".join(death_lines)

    except Exception as e:
        print(f"Error processing death information: {e}")
        import traceback
        print(traceback.format_exc())
        return None
