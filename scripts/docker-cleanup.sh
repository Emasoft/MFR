#!/bin/bash
# Docker cleanup script to save disk space

echo "=== Docker Cleanup Script ==="
echo "This will remove ALL Docker containers, images, volumes, and build cache"
echo ""

# Stop all running containers
echo "1. Stopping all running containers..."
docker stop "$(docker ps -aq)" 2>/dev/null || echo "No running containers"

# Remove all containers
echo "2. Removing all containers..."
docker rm -f "$(docker ps -aq)" 2>/dev/null || echo "No containers to remove"

# Remove all images
echo "3. Removing all images..."
docker rmi -f "$(docker images -aq)" 2>/dev/null || echo "No images to remove"

# Remove all volumes
echo "4. Removing all volumes..."
docker volume rm -f "$(docker volume ls -q)" 2>/dev/null || echo "No volumes to remove"

# System prune with volumes
echo "5. Running system prune..."
docker system prune -a --volumes -f

# Show final disk usage
echo ""
echo "=== Final Docker Disk Usage ==="
docker system df

echo ""
echo "Docker cleanup complete!"
