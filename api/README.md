# Downtube API - Docker Deployment Guide

## Quick Start

### Local Development

```bash
cd api
docker-compose up -d
```

The API will be available at `http://localhost:8000`

### Production Deployment

1. **Copy the environment file:**

    ```bash
    cp .env.example .env
    ```

2. **Edit `.env` to configure your port:**

    ```bash
    API_PORT=8000  # Change to any available port on your server
    ```

3. **Build and run:**
    ```bash
    docker-compose up -d
    ```

## Integration with Other Services

### Using in a Multi-Service Server

If you have other services on your server, you can either:

#### Option 1: Include in Master Compose File

Add this to your main `docker-compose.yml`:

```yaml
services:
    downtube-api:
        image: ghcr.io/erikdoytchinov/downtube-api:latest
        # or build from source:
        # build: ./path/to/downtube/api
        container_name: downtube-api
        restart: unless-stopped
        ports:
            - "8000:8000"
        volumes:
            - ./downtube-downloads:/app/downloads
            - ./www.youtube.com_cookies.txt:/app/www.youtube.com_cookies.txt:ro
        networks:
            - your-network

    # ... your other services
```

#### Option 2: Use External Network

Connect to a shared network:

```bash
# In your main docker-compose.yml
networks:
  shared-network:
    external: true

# Then run downtube-api with:
docker-compose --project-name downtube up -d
```

### Behind a Reverse Proxy (Nginx/Traefik)

Example nginx configuration:

```nginx
location /api/ {
    proxy_pass http://downtube-api:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Docker Commands

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down

# Restart the service
docker-compose restart

# Check health status
docker ps
```

## Environment Variables

- `API_PORT`: Host port to expose (default: 8000)
- `PORT`: Internal container port (default: 8000, don't change unless needed)

## Volumes

- `./downloads`: Stores downloaded videos (persisted)
- `./www.youtube.com_cookies.txt`: YouTube cookies (optional, read-only)

## Health Checks

The container includes a health check that runs every 30 seconds. Check status:

```bash
docker ps
# Look for "healthy" in the STATUS column
```

## Troubleshooting

### Port conflicts

If port 8000 is already in use, change `API_PORT` in `.env`:

```bash
API_PORT=9000
```

### Check container logs

```bash
docker-compose logs -f downtube-api
```

### Access container shell

```bash
docker-compose exec downtube-api /bin/bash
```

## Building for Production

### Build and Push to Registry

```bash
# Build the image
docker build -t downtube-api:latest .

# Tag for registry
docker tag downtube-api:latest ghcr.io/erikdoytchinov/downtube-api:latest

# Push to registry
docker push ghcr.io/erikdoytchinov/downtube-api:latest
```

### Pull and Run on Server

```bash
docker pull ghcr.io/erikdoytchinov/downtube-api:latest
docker-compose up -d
```
