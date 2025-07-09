#!/bin/bash

# YouTube Service Restart Script

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
    echo "║                 🔄 YouTube Service Restart                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

restart_service() {
    log_info "Restarting YouTube service..."
    
    cd "$PROJECT_ROOT"
    
    # Restart the service
    docker-compose -f docker-compose.ytdlp.yml restart yt-dlp-service
    
    log_success "Service restart initiated"
}

rebuild_and_restart() {
    log_info "Rebuilding and restarting YouTube service..."
    
    cd "$PROJECT_ROOT"
    
    # Stop, rebuild, and start
    docker-compose -f docker-compose.ytdlp.yml down
    docker-compose -f docker-compose.ytdlp.yml build --no-cache yt-dlp-service
    docker-compose -f docker-compose.ytdlp.yml up -d
    
    log_success "Service rebuilt and started"
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

verify_restart() {
    log_info "Verifying restart..."
    
    # Get service health and version
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        local health_response=$(curl -s http://localhost:8080/health)
        local version=$(echo "$health_response" | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
        
        log_success "Service restarted successfully!"
        echo "  yt-dlp version: $version"
        return 0
    else
        log_error "Service is not responding after restart"
        return 1
    fi
}

main() {
    local rebuild=false
    local force=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rebuild|-r)
                rebuild=true
                shift
                ;;
            --force|-f)
                force=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_header
    
    # Check if service exists
    if ! docker ps -a | grep -q "yt-dlp-service"; then
        log_warning "YouTube service container not found"
        log_info "Use ./scripts/setup-youtube.sh to set up the service first"
        exit 1
    fi
    
    if [ "$rebuild" = "true" ]; then
        rebuild_and_restart
    else
        restart_service
    fi
    
    if wait_for_service; then
        if verify_restart; then
            echo ""
            echo -e "${BLUE}📍 Service Details:${NC}"
            echo "   🌐 URL: http://localhost:8080"
            echo "   🔍 Health: curl http://localhost:8080/health"
            echo "   📋 Status: ./scripts/youtube-status.sh"
            echo "   🧪 Test: ./scripts/youtube-test.sh"
            echo ""
        else
            log_error "Restart verification failed"
            echo ""
            echo "Check logs: ./scripts/youtube-logs.sh"
            exit 1
        fi
    else
        log_error "Service failed to start after restart"
        echo ""
        echo "Try: ./scripts/youtube-restart.sh --rebuild"
        exit 1
    fi
}

# Handle help
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Restart Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h      Show this help message"
        echo "  --rebuild, -r   Rebuild container before restarting"
        echo "  --force, -f     Force restart (same as rebuild for now)"
        echo ""
        echo "This script restarts the YouTube service."
        echo "Use --rebuild for a complete rebuild with latest yt-dlp."
        echo ""
        echo "Related commands:"
        echo "  ./scripts/youtube-start.sh     - Start the service"
        echo "  ./scripts/youtube-stop.sh      - Stop the service"
        echo "  ./scripts/youtube-status.sh    - Check service status"
        echo ""
        exit 0
        ;;
esac

main "$@"