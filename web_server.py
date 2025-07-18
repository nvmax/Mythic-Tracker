import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mythic_tracker_web')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html', bot_invite_url=config.BOT_INVITE_URL)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup page for configuring the bot"""
    if request.method == 'POST':
        server_id = request.form.get('server_id')
        channel_id = request.form.get('channel_id')

        if not server_id or not channel_id:
            flash('Please provide both server ID and channel ID', 'error')
            return redirect(url_for('setup'))

        try:
            # Validate IDs (they should be numeric)
            server_id = str(int(server_id))
            channel_id = str(int(channel_id))

            # Create a new database connection specifically for this request
            from database import Database
            db_instance = None

            try:
                db_instance = Database()

                # Save to database
                logger.info(f"Attempting to set channel {channel_id} for server {server_id} via web")
                success = db_instance.set_server_channel(server_id, channel_id)
            finally:
                # Make sure to close the database connection even if an error occurs
                if db_instance:
                    db_instance.close()

            if success:
                logger.info(f"Successfully set channel {channel_id} for server {server_id} via web")
                flash('Channel successfully configured!', 'success')
                return redirect(url_for('success'))
            else:
                logger.error(f"Failed to set channel {channel_id} for server {server_id} via web")
                flash('Failed to save configuration. Please try again.', 'error')
                return redirect(url_for('setup'))

        except ValueError:
            flash('Server ID and channel ID must be numbers', 'error')
            return redirect(url_for('setup'))
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            flash(f'An error occurred: {e}', 'error')
            return redirect(url_for('setup'))

    return render_template('setup.html')

@app.route('/success')
def success():
    """Success page after setting up the bot"""
    return render_template('success.html')

@app.route('/help')
def help_page():
    """Help page with instructions"""
    return render_template('help.html')

def run_web_server():
    """Run the web server"""
    try:
        logger.info(f"Starting web server on {config.WEB_HOST}:{config.WEB_PORT}")
        app.run(
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            debug=config.WEB_DEBUG
        )
    except Exception as e:
        logger.error(f"Error running web server: {e}")

if __name__ == "__main__":
    run_web_server()
