#!/bin/bash

# YouTube Service Reset Script
# Complete reset and rebuild of the YouTube service

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
    echo "║                 🔄 YouTube Service Reset                     ║"
    echo "║              Complete Rebuild and Reset                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

confirm_reset() {
    echo -e "${YELLOW}⚠️  This will completely reset the YouTube service:${NC}"
    echo "   • Stop and remove containers"
    echo "   • Remove Docker images"
    echo "   • Clear logs and temporary files"
    echo "   • Rebuild from scratch"
    echo ""
    
    if [ "${1:-}" != "--force" ]; then
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Reset cancelled."
            exit 0
        fi
    else
        log_warning "Force reset mode - skipping confirmation"
    fi
}

stop_service() {
    log_info "Stopping YouTube service..."
    
    cd "$PROJECT_ROOT"
    
    # Stop all related services
    docker-compose -f docker-compose.ytdlp.yml down --remove-orphans 2>/dev/null || true
    
    log_success "Service stopped"
}

remove_containers() {
    log_info "Removing containers..."
    
    # Remove yt-dlp service container
    docker rm -f yt-dlp-service 2>/dev/null || true
    
    # Remove watchtower if it exists
    docker rm -f watchtower 2>/dev/null || true
    
    log_success "Containers removed"
}

remove_images() {
    log_info "Removing Docker images..."
    
    # Remove custom yt-dlp images
    docker rmi $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "yt-dlp" || true) 2>/dev/null || true
    
    # Remove watchtower image
    docker rmi containrrr/watchtower 2>/dev/null || true
    
    log_success "Images removed"
}

clean_volumes() {
    log_info "Cleaning volumes and networks..."
    
    # Remove any orphaned volumes
    docker volume prune -f > /dev/null 2>&1 || true
    
    # Remove networks created by docker-compose
    docker network rm whatsappbot_default 2>/dev/null || true
    
    log_success "Volumes and networks cleaned"
}

clear_logs() {
    log_info "Clearing logs and temporary files..."
    
    # Clear monitoring logs
    if [ -f "/var/log/youtube-system/monitor.log" ]; then
        sudo truncate -s 0 /var/log/youtube-system/monitor.log 2>/dev/null || true
    fi
    
    # Clear application logs
    if [ -f "$PROJECT_ROOT/logs/youtube_downloader.log" ]; then
        truncate -s 0 "$PROJECT_ROOT/logs/youtube_downloader.log" 2>/dev/null || true
    fi
    
    # Remove temp files
    rm -f /tmp/youtube-last-update 2>/dev/null || true
    rm -f /tmp/youtube-*.tmp 2>/dev/null || true
    
    log_success "Logs and temporary files cleared"
}

remove_monitoring() {
    log_info "Removing monitoring setup..."
    
    # Remove cron job
    if crontab -l 2>/dev/null | grep -q "youtube-monitor"; then
        (crontab -l 2>/dev/null | grep -v "youtube-monitor") | crontab - 2>/dev/null || true
        log_success "Monitoring cron job removed"
    fi
    
    # Remove monitoring script
    if [ -f "/usr/local/bin/youtube-monitor.sh" ]; then
        sudo rm -f /usr/local/bin/youtube-monitor.sh 2>/dev/null || true
        log_success "Monitoring script removed"
    fi
    
    # Clear monitoring directory
    if [ -d "/var/log/youtube-system" ]; then
        sudo rm -rf /var/log/youtube-system 2>/dev/null || true
        log_success "Monitoring directory removed"
    fi
}

rebuild_service() {
    log_info "Rebuilding YouTube service from scratch..."
    
    cd "$PROJECT_ROOT"
    
    # Build with no cache to ensure latest everything
    docker-compose -f docker-compose.ytdlp.yml build --no-cache
    
    log_success "Service rebuilt"
}

start_service() {
    log_info "Starting rebuilt service..."
    
    cd "$PROJECT_ROOT"
    
    # Start the service
    docker-compose -f docker-compose.ytdlp.yml up -d
    
    log_success "Service started"
}

wait_for_service() {
    log_info "Waiting for service to be ready..."
    
    local max_retries=60  # Longer timeout for rebuild
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

reinstall_monitoring() {
    log_info "Reinstalling monitoring..."
    
    # Run the monitoring setup from setup-youtube.sh
    if [ -f "$SCRIPT_DIR/setup-youtube.sh" ]; then
        # Extract monitoring setup function and run it
        bash -c "source $SCRIPT_DIR/setup-youtube.sh; setup_monitoring" 2>/dev/null || {
            log_warning "Could not reinstall monitoring automatically"
            echo "Run: ./scripts/setup-youtube.sh to reinstall monitoring"
        }
    else
        log_warning "Setup script not found - monitoring not reinstalled"
    fi
}

verify_reset() {
    log_info "Verifying reset..."
    
    # Check service health
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        local health_response=$(curl -s http://localhost:8080/health)
        local version=$(echo "$health_response" | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
        
        log_success "Reset verification passed!"
        echo "  yt-dlp version: $version"
        
        # Quick functionality test
        log_info "Running quick functionality test..."
        if "$SCRIPT_DIR/youtube-test.sh" health > /dev/null 2>&1; then
            log_success "Functionality test passed!"
        else
            log_warning "Functionality test had issues"
        fi
        
        return 0
    else
        log_error "Reset verification failed - service not responding"
        return 1
    fi
}

print_summary() {
    echo -e "\n${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 Reset Complete!                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${GREEN}✅ YouTube service has been completely reset and rebuilt${NC}"
    echo ""
    echo -e "${BLUE}📍 Service Details:${NC}"
    echo "   🌐 URL: http://localhost:8080"
    echo "   🔍 Health: curl http://localhost:8080/health"
    echo "   📊 Status: ./scripts/youtube-status.sh"
    echo "   🧪 Test: ./scripts/youtube-test.sh"
    echo ""
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo "   ./scripts/youtube-restart.sh  - Restart service"
    echo "   ./scripts/youtube-logs.sh     - View logs"
    echo "   ./scripts/youtube-update.sh   - Update yt-dlp"
    echo "   ./scripts/youtube-monitor.sh  - Monitor service"
    echo ""
}

main() {
    local force=false
    local keep_monitoring=false
    local keep_logs=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                force=true
                shift
                ;;
            --keep-monitoring)
                keep_monitoring=true
                shift
                ;;
            --keep-logs)
                keep_logs=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    print_header
    
    if [ "$force" = true ]; then
        confirm_reset --force
    else
        confirm_reset
    fi
    
    log_info "Starting complete reset process..."
    
    # Cleanup phase
    stop_service
    remove_containers
    remove_images
    clean_volumes
    
    if [ "$keep_logs" != true ]; then
        clear_logs
    fi
    
    if [ "$keep_monitoring" != true ]; then
        remove_monitoring
    fi
    
    # Rebuild phase
    rebuild_service
    start_service
    
    if wait_for_service; then
        if [ "$keep_monitoring" != true ]; then
            reinstall_monitoring
        fi
        
        if verify_reset; then
            print_summary
            log_success "YouTube service reset completed successfully!"
            exit 0
        else
            log_error "Reset verification failed"
            echo "Check logs: ./scripts/youtube-logs.sh"
            exit 1
        fi
    else
        log_error "Service failed to start after reset"
        echo "Check logs: ./scripts/youtube-logs.sh"
        exit 1
    fi
}

# Handle help
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Reset Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h          Show this help message"
        echo "  --force, -f         Skip confirmation prompt"
        echo "  --keep-monitoring   Don't remove monitoring setup"
        echo "  --keep-logs         Don't clear log files"
        echo ""
        echo "This script performs a complete reset of the YouTube service:"
        echo "  • Stops and removes all containers"
        echo "  • Removes Docker images"
        echo "  • Clears logs and temporary files"
        echo "  • Removes monitoring (unless --keep-monitoring)"
        echo "  • Rebuilds everything from scratch"
        echo "  • Reinstalls monitoring"
        echo ""
        echo "⚠️  WARNING: This is a destructive operation!"
        echo ""
        echo "Less destructive alternatives:"
        echo "  ./scripts/youtube-restart.sh --rebuild  - Just rebuild container"
        echo "  ./scripts/youtube-update.sh --force     - Force update yt-dlp"
        echo ""
        exit 0
        ;;
esac

main "$@"