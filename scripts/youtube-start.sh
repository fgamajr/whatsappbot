#!/bin/bash

# YouTube Service Start Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                  ▶️  YouTube Service Start                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_if_running() {
    if docker ps | grep -q "yt-dlp-service"; then
        log_warning "YouTube service is already running"
        echo "Use ./scripts/youtube-restart.sh to restart or ./scripts/youtube-status.sh to check status"
        exit 0
    fi
}

start_service() {
    log_info "Starting YouTube service..."
    
    cd "$PROJECT_ROOT"
    
    # Start the service
    docker-compose -f docker-compose.ytdlp.yml up -d
    
    log_success "Service startup initiated"
}

wait_for_service() {
    log_info "Waiting for service to be ready..."
    
    local max_retries=30
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Service is ready!"
            return 0
        else
            echo -n "."
            sleep 2
            retry_count=$((retry_count + 1))
        fi
    done
    
    echo ""
    log_error "Service failed to start within timeout"
    return 1
}

main() {
    print_header
    
    check_if_running
    start_service
    
    if wait_for_service; then
        log_success "YouTube service started successfully!"
        echo ""
        echo -e "${BLUE}📍 Service Details:${NC}"
        echo "   🌐 URL: http://localhost:8080"
        echo "   🔍 Health: curl http://localhost:8080/health"
        echo "   📋 Status: ./scripts/youtube-status.sh"
        echo ""
    else
        log_error "Failed to start service"
        echo ""
        echo "Check logs: ./scripts/youtube-logs.sh"
        exit 1
    fi
}

# Handle help
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Start Script"
        echo ""
        echo "Usage: $0"
        echo ""
        echo "This script starts the YouTube service if it's not already running."
        echo ""
        echo "Related commands:"
        echo "  ./scripts/youtube-stop.sh     - Stop the service"
        echo "  ./scripts/youtube-restart.sh  - Restart the service"
        echo "  ./scripts/youtube-status.sh   - Check service status"
        echo ""
        exit 0
        ;;
esac

main "$@"