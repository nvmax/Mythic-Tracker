# Docker Deployment Guide for Mythic Tracker

This guide explains how to deploy the Mythic Tracker Discord bot using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- A Discord bot token (from Discord Developer Portal)
- A Raider.io API access key (optional, but recommended)

## Quick Start

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/nvmax/Mythic-Tracker.git
   cd Mythic-Tracker
   ```

2. **Create your environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit the `.env` file** with your configuration:
   ```bash
   nano .env  # or use your preferred editor
   ```
   
   Required fields:
   - `DISCORD_TOKEN`: Your Discord bot token
   - `API_ACCESS_KEY`: Your Raider.io API key
   - `FLASK_SECRET_KEY`: A random secret key for Flask sessions
   - `BOT_INVITE_URL`: Replace `YOUR_CLIENT_ID` with your bot's client ID

4. **Create the data directory**:
   ```bash
   mkdir -p data
   ```

5. **Build and run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

## Docker Commands

### Build and Start
```bash
# Build and start in detached mode
docker-compose up -d

# Build and start with logs visible
docker-compose up

# Force rebuild
docker-compose up --build
```

### Management
```bash
# View logs
docker-compose logs -f

# Stop the container
docker-compose down

# Restart the container
docker-compose restart

# View container status
docker-compose ps
```

### Manual Docker Build
If you prefer to use Docker directly without Compose:

```bash
# Build the image
docker build -t mythic-tracker .

# Run the container
docker run -d \
  --name mythic-tracker \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  -e DATABASE_FILE=/app/data/mythictracker.db \
  mythic-tracker
```

## Configuration

### Environment Variables

The application uses the following environment variables (defined in `.env`):

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DISCORD_TOKEN` | Discord bot token | Yes | - |
| `CHECK_INTERVAL` | Check interval in seconds | Yes | 60 |
| `DATABASE_FILE` | Database file path | Yes | mythictracker.db |
| `RAIDERIO_API_URL` | Raider.io API base URL | Yes | https://raider.io/api/v1 |
| `API_ACCESS_KEY` | Raider.io API access key | Yes | - |
| `FLASK_SECRET_KEY` | Flask session secret key | Yes | - |
| `FLASK_HOST` | Flask host binding | No | 0.0.0.0 |
| `FLASK_PORT` | Flask port | No | 5000 |
| `BOT_INVITE_URL` | Bot invitation URL | Yes | - |
| `ALLOWED_CHANNELS` | Allowed channel names | No | mythic-tracker,bot-commands,general |

### Persistent Data

The Docker setup uses volumes to persist data:

- **Database**: Stored in `./data/mythictracker.db` on the host
- **Configuration**: The `.env` file is mounted read-only

### Ports

- **5000**: Web interface (mapped to host port 5000)

## Accessing the Application

Once running, you can access:

- **Web Interface**: http://localhost:5000
- **Discord Bot**: Invite the bot to your Discord server using the URL in your `.env` file

## Troubleshooting

### Check Container Logs
```bash
docker-compose logs -f mythic-tracker
```

### Check Container Status
```bash
docker-compose ps
```

### Restart Container
```bash
docker-compose restart mythic-tracker
```

### Access Container Shell
```bash
docker-compose exec mythic-tracker bash
```

### Common Issues

1. **Permission Denied on Data Directory**:
   ```bash
   sudo chown -R 1000:1000 data/
   ```

2. **Port Already in Use**:
   Change the port mapping in `docker-compose.yml`:
   ```yaml
   ports:
     - "5001:5000"  # Use port 5001 instead
   ```

3. **Environment Variables Not Loading**:
   Ensure your `.env` file is in the same directory as `docker-compose.yml`

## Security Considerations

- The container runs as a non-root user for security
- The `.env` file is mounted read-only
- Database is stored in a mounted volume for persistence
- Health checks are configured to monitor application status

## Updating

To update the application:

1. Pull the latest code:
   ```bash
   git pull origin main
   ```

2. Rebuild and restart:
   ```bash
   docker-compose down
   docker-compose up --build -d
   ```

## Production Deployment

For production deployment, consider:

1. **Use a reverse proxy** (nginx, Traefik) for HTTPS
2. **Set up log rotation** for container logs
3. **Configure monitoring** and alerting
4. **Regular backups** of the data directory
5. **Use Docker secrets** for sensitive environment variables
