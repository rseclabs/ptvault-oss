#!/bin/bash

# PTVault Docker Build and Run Script
# This script builds and runs PTVault in a Docker container

set -e

echo "=== PTVault Docker Build Script ==="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "WARNING: docker-compose not found. Install it for easier management."
    echo "You can still use 'docker build' and 'docker run' commands."
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found!"
    echo "Creating .env from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Signing secrets are generated on first start and kept in ./data."
    else
        echo "ERROR: .env.example not found!"
        exit 1
    fi
fi

# Parse command line arguments
ACTION=${1:-build}

case $ACTION in
    build)
        echo "Building Docker image..."
        docker build -t ptvault:latest .
        echo ""
        echo "=== Build Successful ==="
        echo ""
        echo "To run PTVault:"
        echo "  ./build_docker.sh run"
        echo ""
        echo "Or with docker-compose:"
        echo "  docker-compose up -d"
        ;;

    run)
        echo "Starting PTVault container..."

        # Create data directory if it doesn't exist
        mkdir -p ./data

        # Stop existing container if running
        docker stop ptvault 2>/dev/null || true
        docker rm ptvault 2>/dev/null || true

        # Run container
        docker run -d \
            --name ptvault \
            -p 5000:5000 \
            -v $(pwd)/data:/app/data \
            -v $(pwd)/.env:/app/.env:ro \
            --restart unless-stopped \
            ptvault:latest

        echo ""
        echo "=== PTVault Started ==="
        echo ""
        echo "Access PTVault at: http://localhost:5000"
        echo ""
        echo "Useful commands:"
        echo "  View logs:    docker logs -f ptvault"
        echo "  Stop:         docker stop ptvault"
        echo "  Restart:      docker restart ptvault"
        echo "  Remove:       docker rm -f ptvault"
        ;;

    stop)
        echo "Stopping PTVault container..."
        docker stop ptvault
        echo "PTVault stopped."
        ;;

    logs)
        echo "Showing PTVault logs (Ctrl+C to exit)..."
        docker logs -f ptvault
        ;;

    shell)
        echo "Opening shell in PTVault container..."
        docker exec -it ptvault /bin/bash
        ;;

    *)
        echo "Usage: $0 {build|run|stop|logs|shell}"
        echo ""
        echo "Commands:"
        echo "  build  - Build the Docker image"
        echo "  run    - Run PTVault in a container"
        echo "  stop   - Stop the running container"
        echo "  logs   - View container logs"
        echo "  shell  - Open a shell in the container"
        exit 1
        ;;
esac
