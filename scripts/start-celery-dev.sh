#!/bin/bash

# Start Celery Development Environment
# This script starts all Celery services for local development

set -e

echo "🚀 Starting WhatsApp Interview Bot with Celery..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed!"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found! Creating template..."
    cp .env.example .env 2>/dev/null || echo "# Please configure your .env file" > .env
    print_warning "Please configure your .env file with the required secrets"
fi

# Function to check service health
check_service_health() {
    local service_name=$1
    local max_attempts=30
    local attempt=1
    
    print_step "Checking $service_name health..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f docker-compose.celery.yml ps $service_name | grep -q "Up (healthy)"; then
            print_status "$service_name is healthy!"
            return 0
        elif docker-compose -f docker-compose.celery.yml ps $service_name | grep -q "Up"; then
            print_step "$service_name is up, waiting for health check... (attempt $attempt/$max_attempts)"
        else
            print_step "$service_name is starting... (attempt $attempt/$max_attempts)"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_warning "$service_name health check timeout"
    return 1
}

# Stop any existing services
print_step "Stopping existing services..."
docker-compose -f docker-compose.celery.yml down --remove-orphans

# Build and start services
print_step "Building and starting services..."
docker-compose -f docker-compose.celery.yml up -d --build

# Wait for Redis to be healthy
check_service_health "redis"

# Wait for the app to be healthy
check_service_health "app"

# Check Celery workers
print_step "Checking Celery workers..."
sleep 5

# Show service status
print_step "Service Status:"
docker-compose -f docker-compose.celery.yml ps

# Show logs for a few seconds
print_step "Recent logs:"
docker-compose -f docker-compose.celery.yml logs --tail=10

# Test Celery connection
print_step "Testing Celery connection..."
if docker-compose -f docker-compose.celery.yml exec -T celery-worker-general celery -A app.celery_app inspect ping 2>/dev/null | grep -q "pong"; then
    print_status "✅ Celery workers are responding!"
else
    print_warning "⚠️  Celery workers may not be ready yet"
fi

print_status "🎉 Setup complete!"
echo ""
echo "📊 Access points:"
echo "  - Application: http://localhost:8000"
echo "  - Health Check: http://localhost:8000/health/ready"
echo "  - Celery Monitor (Flower): http://localhost:5555 (admin:admin123)"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "🧪 Test Celery:"
echo "  curl -X POST http://localhost:8000/celery/test -H 'Content-Type: application/json' -d '{\"x\": 4, \"y\": 4}'"
echo ""
echo "📋 Useful commands:"
echo "  - View logs: docker-compose -f docker-compose.celery.yml logs -f [service]"
echo "  - Scale workers: docker-compose -f docker-compose.celery.yml up -d --scale celery-worker-audio=3"
echo "  - Stop all: docker-compose -f docker-compose.celery.yml down"
echo ""
print_status "Happy coding! 🚀"