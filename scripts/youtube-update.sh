#!/bin/bash

# YouTube Service Update Script
# Updates yt-dlp to the latest version

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
    echo "║                  🔄 YouTube Service Update                   ║"
    echo "║                    yt-dlp Version Update                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_service_status() {
    log_info "Checking service status..."
    
    if ! curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        log_error "Service is not responding. Please start the service first."
        echo "Run: ./scripts/youtube-start.sh"
        exit 1
    fi
    
    log_success "Service is responding"
}

get_current_version() {
    log_info "Getting current yt-dlp version..."
    
    CURRENT_VERSION=$(curl -s http://localhost:8080/health | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$CURRENT_VERSION" ]; then
        log_info "Current version: $CURRENT_VERSION"
        echo "$CURRENT_VERSION"
    else
        log_warning "Could not determine current version"
        echo "unknown"
    fi
}

update_via_service() {
    log_info "Requesting service to update yt-dlp..."
    
    UPDATE_RESPONSE=$(curl -s -X POST http://localhost:8080/update)
    
    # Parse response
    SUCCESS=$(echo "$UPDATE_RESPONSE" | grep -o '"success":[^,]*' | cut -d':' -f2)
    OLD_VERSION=$(echo "$UPDATE_RESPONSE" | grep -o '"old_version":"[^"]*"' | cut -d'"' -f4)
    NEW_VERSION=$(echo "$UPDATE_RESPONSE" | grep -o '"new_version":"[^"]*"' | cut -d'"' -f4)
    MESSAGE=$(echo "$UPDATE_RESPONSE" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$SUCCESS" = "true" ]; then
        log_success "Update completed successfully!"
        echo "  Old version: $OLD_VERSION"
        echo "  New version: $NEW_VERSION"
        echo "  Message: $MESSAGE"
        return 0
    else
        log_error "Update failed!"
        echo "  Message: $MESSAGE"
        echo "  Full response: $UPDATE_RESPONSE"
        return 1
    fi
}

rebuild_container() {
    log_info "Rebuilding container with latest yt-dlp..."
    
    cd "$PROJECT_ROOT"
    
    # Stop the service
    log_info "Stopping service..."
    docker-compose -f docker-compose.ytdlp.yml down
    
    # Rebuild with no cache to ensure latest yt-dlp
    log_info "Rebuilding container (this may take a few minutes)..."
    docker-compose -f docker-compose.ytdlp.yml build --no-cache yt-dlp-service
    
    # Start the service
    log_info "Starting updated service..."
    docker-compose -f docker-compose.ytdlp.yml up -d
    
    # Wait for service to be ready
    log_info "Waiting for service to be ready..."
    local max_retries=30
    local retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Service is ready after rebuild!"
            return 0
        else
            log_info "Service not ready yet... (attempt $((retry_count + 1))/$max_retries)"
            sleep 5
            retry_count=$((retry_count + 1))
        fi
    done
    
    log_error "Service failed to start after rebuild"
    return 1
}

verify_update() {
    log_info "Verifying update..."
    
    # Get new version
    NEW_VERSION=$(curl -s http://localhost:8080/health | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$NEW_VERSION" ]; then
        log_success "Update verified! New version: $NEW_VERSION"
        
        # Test basic functionality
        log_info "Testing basic functionality..."
        
        TEST_RESPONSE=$(curl -s -X POST http://localhost:8080/download \
            -H "Content-Type: application/json" \
            -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "max_file_size": 1048576}' \
            --max-time 30)
        
        if echo "$TEST_RESPONSE" | grep -q '"success"'; then
            log_success "Functionality test passed!"
        else
            log_warning "Functionality test had issues, but version update was successful"
            echo "Test response: $TEST_RESPONSE"
        fi
        
        return 0
    else
        log_error "Could not verify new version"
        return 1
    fi
}

check_latest_version() {
    log_info "Checking latest available yt-dlp version..."
    
    # Get latest version from GitHub API
    LATEST_VERSION=$(curl -s https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest | grep -o '"tag_name":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$LATEST_VERSION" ]; then
        log_info "Latest available version: $LATEST_VERSION"
        echo "$LATEST_VERSION"
    else
        log_warning "Could not determine latest version from GitHub"
        echo "unknown"
    fi
}

compare_versions() {
    local current="$1"
    local latest="$2"
    
    if [ "$current" = "$latest" ]; then
        log_info "Already running the latest version!"
        return 1  # No update needed
    else
        log_info "Update available: $current → $latest"
        return 0  # Update needed
    fi
}

print_summary() {
    echo -e "\n${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    📊 Update Summary                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Get final version
    FINAL_VERSION=$(curl -s http://localhost:8080/health | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
    
    echo -e "${GREEN}✅ Update Process Complete${NC}"
    echo "   Final yt-dlp version: $FINAL_VERSION"
    echo ""
    echo -e "${BLUE}🔧 Service Status:${NC}"
    ./scripts/youtube-status.sh --summary
}

main() {
    print_header
    
    local force_rebuild=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                force_rebuild=true
                shift
                ;;
            --rebuild|-r)
                force_rebuild=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_service_status
    
    current_version=$(get_current_version)
    
    if [ "$force_rebuild" = true ]; then
        log_info "Force rebuild requested..."
        if rebuild_container; then
            verify_update
            print_summary
        else
            log_error "Rebuild failed"
            exit 1
        fi
    else
        # Try service update first
        log_info "Attempting in-service update..."
        
        if update_via_service; then
            verify_update
            print_summary
        else
            log_warning "In-service update failed, trying container rebuild..."
            
            if rebuild_container; then
                verify_update
                print_summary
            else
                log_error "Both update methods failed"
                exit 1
            fi
        fi
    fi
    
    log_success "Update process completed!"
}

# Handle help
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Update Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h      Show this help message"
        echo "  --force, -f     Force container rebuild (slower but more reliable)"
        echo "  --rebuild, -r   Same as --force"
        echo ""
        echo "Update Methods:"
        echo "  1. In-service update (fast) - Updates yt-dlp without rebuilding container"
        echo "  2. Container rebuild (slow) - Rebuilds entire container with latest yt-dlp"
        echo ""
        echo "The script tries in-service update first, then falls back to rebuild if needed."
        echo ""
        exit 0
        ;;
esac

# Run main function
main "$@"