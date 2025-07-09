#!/bin/bash

# YouTube Service Stop Script

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
    echo "║                  ⏹️  YouTube Service Stop                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_if_running() {
    if ! docker ps | grep -q "yt-dlp-service"; then
        log_warning "YouTube service is not currently running"
        exit 0
    fi
}

stop_service() {
    log_info "Stopping YouTube service..."
    
    cd "$PROJECT_ROOT"
    
    # Stop the service
    docker-compose -f docker-compose.ytdlp.yml down
    
    log_success "Service stopped"
}

verify_stopped() {
    log_info "Verifying service is stopped..."
    
    # Wait a moment for Docker to clean up
    sleep 2
    
    if docker ps | grep -q "yt-dlp-service"; then
        log_error "Service is still running"
        return 1
    else
        log_success "Service is completely stopped"
        return 0
    fi
}

cleanup_resources() {
    local force="${1:-false}"
    
    if [ "$force" = "true" ]; then
        log_info "Performing cleanup..."
        
        # Remove any stopped containers
        docker container prune -f > /dev/null 2>&1 || true
        
        # Clean up any orphaned volumes (be careful here)
        # docker volume prune -f > /dev/null 2>&1 || true
        
        log_success "Cleanup completed"
    fi
}

main() {
    local force_cleanup=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cleanup|-c)
                force_cleanup=true
                shift
                ;;
            --force|-f)
                # Force stop even if not responding
                force_cleanup=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_header
    
    check_if_running
    stop_service
    
    if verify_stopped; then
        cleanup_resources "$force_cleanup"
        
        log_success "YouTube service stopped successfully!"
        echo ""
        echo -e "${BLUE}🔧 Available Commands:${NC}"
        echo "   ▶️  Start: ./scripts/youtube-start.sh"
        echo "   🔄 Restart: ./scripts/youtube-restart.sh"
        echo "   📊 Status: ./scripts/youtube-status.sh"
        echo ""
    else
        log_error "Failed to stop service completely"
        echo ""
        echo "Try force stop: $0 --force"
        exit 1
    fi
}

# Handle help
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Stop Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h      Show this help message"
        echo "  --cleanup, -c   Perform cleanup after stopping"
        echo "  --force, -f     Force stop and cleanup"
        echo ""
        echo "This script stops the YouTube service gracefully."
        echo ""
        echo "Related commands:"
        echo "  ./scripts/youtube-start.sh     - Start the service"
        echo "  ./scripts/youtube-restart.sh   - Restart the service"
        echo "  ./scripts/youtube-status.sh    - Check service status"
        echo ""
        exit 0
        ;;
esac

main "$@"