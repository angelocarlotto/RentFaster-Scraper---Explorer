# RentFaster Scraper - Docker Setup

## Quick Start

### Build and Run with Docker Compose

```bash
# Build and start the web application
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop the application
docker-compose down
```

The web application will be available at: **http://localhost:5001**

## Docker Services

### Web Application (Default)
- **Port**: 5001
- **Database**: Uses `rentfaster_detailed_offline.json`
- **Auto-restart**: Yes
- **Health check**: Enabled

### Requirements

Before running, ensure you have:
1. `rentfaster_detailed_offline.json` - Main database file
2. `rentfaster_listings.json` - Fallback database (optional)
3. `static/` - Static assets folder
4. `templates/` - HTML templates folder

## Docker Commands

```bash
# Build only (without starting)
docker-compose build

# Start in foreground (see logs in terminal)
docker-compose up

# Start in background (detached mode)
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f web

# Restart services
docker-compose restart

# Remove containers and volumes
docker-compose down -v
```

## Manual Docker Build

If you prefer to use Docker directly without compose:

```bash
# Build the image
docker build -t rentfaster-web .

# Run the container
docker run -d \
  --name rentfaster-web \
  -p 5001:5001 \
  -v $(pwd)/rentfaster_detailed_offline.json:/app/rentfaster_detailed_offline.json:ro \
  -v $(pwd)/static:/app/static:ro \
  -v $(pwd)/templates:/app/templates:ro \
  rentfaster-web

# View logs
docker logs -f rentfaster-web

# Stop and remove
docker stop rentfaster-web
docker rm rentfaster-web
```

## Production Deployment

For production, consider using `gunicorn` instead of Flask's development server:

Update `CMD` in Dockerfile:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "web_app:app"]
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs web

# Check if port is already in use
lsof -i :5001
```

### Database file not found
Ensure `rentfaster_detailed_offline.json` exists in the project root before starting Docker.

### Permission issues
```bash
# Fix file permissions
chmod 644 rentfaster_detailed_offline.json
chmod 755 static/ templates/
```

## Health Check

The container includes a health check that runs every 30 seconds:
```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' rentfaster_web
```

## Environment Variables

You can customize the application using environment variables:

```yaml
environment:
  - FLASK_ENV=production
  - PYTHONUNBUFFERED=1
  - FLASK_APP=web_app.py
```

## Data Volumes

Data files are mounted as **read-only** to prevent accidental modifications:
- `rentfaster_detailed_offline.json:ro`
- `rentfaster_listings.json:ro`
- `static:ro`
- `templates:ro`

If you need to update data, do it on the host machine and restart the container.
