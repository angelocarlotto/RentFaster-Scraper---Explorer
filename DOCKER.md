# Docker Deployment Guide

## Overview
The RentFaster application is now fully containerized with MongoDB support. The Docker setup includes the web interface that connects to your MongoDB database.

## Files Updated
- ✅ `Dockerfile` - Added MongoDB environment variables
- ✅ `docker-compose.yml` - Removed data volume, added MongoDB config
- ✅ `requirements.txt` - Added pymongo and dnspython
- ✅ `scripts/web_app.py` - Reads MongoDB config from environment variables

## Quick Start

### 1. Build and Run
```bash
# Build and start the container
docker-compose up -d --build

# View logs
docker-compose logs -f web

# Stop the container
docker-compose down
```

### 2. Access the Application
- **Local**: http://localhost:5001
- **Network**: http://YOUR_HOST_IP:5001

## Configuration

### MongoDB Connection
The application uses environment variables for MongoDB configuration:

```yaml
environment:
  - MONGO_URI=mongodb://root:PASSWORD@10.0.0.123:27023/?directConnection=true
  - MONGO_DB=rentfaster
  - MONGO_COLLECTION=listings_detailed
```

### Customizing MongoDB Connection
You can override these in `docker-compose.yml` or at runtime:

```bash
# Via docker-compose.yml
docker-compose up -d

# Via command line
docker run -e MONGO_URI="mongodb://..." rentfaster_web
```

## Architecture Changes

### Before (JSON-based)
```yaml
volumes:
  - ./data:/app/data:ro  # Mounted JSON files
```

### After (MongoDB-based)
```yaml
volumes:
  - ./static:/app/static:ro
  - ./templates:/app/templates:ro
  - ./scripts:/app/scripts:ro
  # No data volume - reads from MongoDB
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://root:...@10.0.0.123:27023/?directConnection=true` | MongoDB connection string |
| `MONGO_DB` | `rentfaster` | Database name |
| `MONGO_COLLECTION` | `listings_detailed` | Collection name |
| `FLASK_ENV` | `production` | Flask environment |
| `PYTHONUNBUFFERED` | `1` | Python output buffering |

## Docker Commands

### Build
```bash
# Build the image
docker build -t rentfaster_web .

# Build with no cache
docker build --no-cache -t rentfaster_web .
```

### Run
```bash
# Run with docker-compose
docker-compose up -d

# Run standalone
docker run -d \
  -p 5001:5001 \
  -e MONGO_URI="mongodb://..." \
  --name rentfaster_web \
  rentfaster_web
```

### Logs
```bash
# Follow logs
docker-compose logs -f web

# View last 100 lines
docker-compose logs --tail=100 web
```

### Management
```bash
# Start/Stop
docker-compose start
docker-compose stop

# Restart
docker-compose restart web

# Remove containers
docker-compose down

# Remove containers and images
docker-compose down --rmi all
```

## Health Check

The container includes a health check that verifies the web app is responding:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5001/', timeout=5)" || exit 1
```

Check health status:
```bash
# Via docker-compose
docker-compose ps

# Via docker
docker inspect --format='{{.State.Health.Status}}' rentfaster_web
```

## Networking

### Container Network
The `docker-compose.yml` creates a bridge network:

```yaml
networks:
  rentfaster_network:
    driver: bridge
```

### MongoDB Access
Ensure your MongoDB server allows connections from the Docker container:
- MongoDB at `10.0.0.123:27023` must be accessible from container
- Check firewall rules
- Verify MongoDB authentication credentials

### Testing Connection
```bash
# Shell into container
docker exec -it rentfaster_web /bin/bash

# Test MongoDB connection
python -c "from pymongo import MongoClient; client = MongoClient('mongodb://...'); print(client.server_info())"
```

## Production Deployment

### Using Gunicorn
For production, use Gunicorn instead of Flask's dev server:

**Update Dockerfile CMD:**
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "scripts.web_app:app"]
```

### Reverse Proxy
Use Nginx or Traefik as a reverse proxy:

**Nginx example:**
```nginx
server {
    listen 80;
    server_name rentfaster.example.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Security Considerations
1. **Remove hardcoded credentials** from `docker-compose.yml`
2. **Use Docker secrets** for sensitive data:
   ```bash
   echo "mongodb://..." | docker secret create mongo_uri -
   ```
3. **Use environment file** instead of inline env vars:
   ```yaml
   env_file:
     - .env.production
   ```

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs web

# Common issues:
# - MongoDB not accessible
# - Port 5001 already in use
# - Missing environment variables
```

### MongoDB Connection Failed
```bash
# Test from container
docker exec -it rentfaster_web python -c "
from pymongo import MongoClient
client = MongoClient('${MONGO_URI}')
print('Connected:', client.server_info()['version'])
"
```

### Port Already in Use
```bash
# Find process using port 5001
lsof -i :5001

# Change port in docker-compose.yml
ports:
  - "5002:5001"  # Host:Container
```

### Health Check Failing
```bash
# Check health status
docker inspect rentfaster_web | grep -A 10 Health

# Manual health check
docker exec rentfaster_web curl -f http://localhost:5001/ || exit 1
```

## Multi-Stage Build (Optional)

For smaller images, use multi-stage builds:

```dockerfile
# Builder stage
FROM python:3.14-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.14-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "scripts/web_app.py"]
```

## Monitoring

### Container Stats
```bash
# Real-time stats
docker stats rentfaster_web

# Resource usage
docker-compose top
```

### Application Logs
```bash
# Follow app logs
docker-compose logs -f web

# Filter by time
docker-compose logs --since 30m web
```

## Backup Strategy

Since data is now in MongoDB, no container backup needed. Just ensure:
1. **MongoDB backups** are configured (mongodump)
2. **Code is in version control** (git)
3. **Configuration is documented** (this file)

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build Docker image
        run: docker build -t rentfaster_web .
      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push rentfaster_web
```

## Scaling

### Multiple Instances
Run multiple containers behind a load balancer:

```yaml
services:
  web:
    # ... config ...
    deploy:
      replicas: 3
    networks:
      - rentfaster_network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - web
```

## Summary

✅ **Docker files updated** for MongoDB  
✅ **Environment variables** for flexible config  
✅ **No data volumes** needed (MongoDB handles storage)  
✅ **Health checks** configured  
✅ **Production ready** with Gunicorn option  

**Key Change**: Application now reads from MongoDB instead of mounting JSON files, making it truly stateless and scalable.
