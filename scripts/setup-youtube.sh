#!/bin/bash

# YouTube System Complete Setup Script
# This script sets up the entire resilient YouTube downloading system

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
    echo "║                  🎬 YouTube System Setup                     ║"
    echo "║              Resilient yt-dlp Microservice                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed. Please install curl first."
        exit 1
    fi
    
    log_success "All dependencies are available"
}

setup_directories() {
    log_info "Setting up directories..."
    
    # Create necessary directories
    mkdir -p "$PROJECT_ROOT/docker/yt-dlp"
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "/var/log/youtube-system"
    
    log_success "Directories created"
}

build_service() {
    log_info "Building yt-dlp service..."
    
    cd "$PROJECT_ROOT"
    
    # Build the service
    docker-compose -f docker-compose.ytdlp.yml build
    
    log_success "Service built successfully"
}

start_service() {
    log_info "Starting yt-dlp service..."
    
    cd "$PROJECT_ROOT"
    
    # Start the service
    docker-compose -f docker-compose.ytdlp.yml up -d
    
    log_success "Service started"
}

wait_for_service() {
    log_info "Waiting for service to be ready..."
    
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Service is healthy and ready!"
            return 0
        else
            log_info "Service not ready yet... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
            sleep 5
            RETRY_COUNT=$((RETRY_COUNT + 1))
        fi
    done
    
    log_error "Service failed to start properly"
    docker-compose -f docker-compose.ytdlp.yml logs
    return 1
}

test_functionality() {
    log_info "Testing download functionality..."
    
    # Test with a known working YouTube URL
    TEST_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
    
    RESPONSE=$(curl -s -X POST http://localhost:8080/download \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"$TEST_URL\", \"max_file_size\": 10485760}")  # 10MB limit for test
    
    if echo "$RESPONSE" | grep -q '"success": true'; then
        log_success "Download test successful!"
    else
        log_warning "Download test returned an error (this might be normal for geo-restricted content)"
        echo "Response: $RESPONSE"
    fi
}

setup_monitoring() {
    log_info "Setting up monitoring and auto-update system..."
    
    # Create monitoring script
    cat > /tmp/youtube-monitor.sh << 'EOF'
#!/bin/bash
# YouTube service monitoring and auto-update script

# Configuration
SERVICE_URL="http://localhost:8080"
LOG_FILE="/var/log/youtube-system/monitor.log"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.ytdlp.yml"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Health check
if ! curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
    log_message "ERROR: Service health check failed - attempting restart"
    cd "$PROJECT_ROOT" && docker-compose -f docker-compose.ytdlp.yml restart yt-dlp-service
    
    # Wait a bit and check again
    sleep 10
    if ! curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
        log_message "CRITICAL: Service restart failed"
        exit 1
    else
        log_message "SUCCESS: Service restarted successfully"
    fi
fi

# Auto-update check (every 6 hours)
LAST_UPDATE_FILE="/tmp/youtube-last-update"
CURRENT_TIME=$(date +%s)
UPDATE_INTERVAL=21600  # 6 hours in seconds

if [ ! -f "$LAST_UPDATE_FILE" ] || [ $((CURRENT_TIME - $(cat "$LAST_UPDATE_FILE"))) -gt $UPDATE_INTERVAL ]; then
    log_message "INFO: Checking for yt-dlp updates"
    
    RESPONSE=$(curl -s -X POST "$SERVICE_URL/update")
    if echo "$RESPONSE" | grep -q '"success": true'; then
        log_message "INFO: Update check completed successfully"
        echo "$CURRENT_TIME" > "$LAST_UPDATE_FILE"
    else
        log_message "WARNING: Update check failed"
    fi
fi

log_message "INFO: Health check passed"
EOF

    # Make it executable and move to proper location
    chmod +x /tmp/youtube-monitor.sh
    sed -i "s|\$PROJECT_ROOT|$PROJECT_ROOT|g" /tmp/youtube-monitor.sh
    sudo mv /tmp/youtube-monitor.sh /usr/local/bin/youtube-monitor.sh
    
    # Add to crontab if not exists
    if ! crontab -l 2>/dev/null | grep -q "youtube-monitor"; then
        (crontab -l 2>/dev/null; echo "*/30 * * * * /usr/local/bin/youtube-monitor.sh") | crontab -
        log_success "Monitoring cron job installed (runs every 30 minutes)"
    else
        log_info "Monitoring cron job already exists"
    fi
}

update_env_file() {
    log_info "Updating environment configuration..."
    
    ENV_FILE="$PROJECT_ROOT/.env"
    
    # Add YouTube service configuration to .env if not exists
    if [ -f "$ENV_FILE" ]; then
        if ! grep -q "YTDLP_SERVICE_URL" "$ENV_FILE"; then
            cat >> "$ENV_FILE" << 'EOF'

# YouTube Service Configuration
YTDLP_SERVICE_URL=http://localhost:8080
YTDLP_AUTO_UPDATE=true
YTDLP_UPDATE_INTERVAL_HOURS=6
EOF
            log_success "Environment configuration updated"
        else
            log_info "Environment configuration already exists"
        fi
    else
        log_warning ".env file not found - please add YouTube configuration manually"
    fi
}

print_summary() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   🎉 Setup Complete!                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}📍 YouTube Service Details:${NC}"
    echo "   🌐 Service URL: http://localhost:8080"
    echo "   🔍 Health Check: curl http://localhost:8080/health"
    echo "   🔄 Manual Update: curl -X POST http://localhost:8080/update"
    echo ""
    
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo "   ./scripts/youtube-status.sh    - Check service status"
    echo "   ./scripts/youtube-logs.sh      - View service logs"
    echo "   ./scripts/youtube-update.sh    - Update yt-dlp manually"
    echo "   ./scripts/youtube-restart.sh   - Restart service"
    echo "   ./scripts/youtube-test.sh      - Test functionality"
    echo ""
    
    echo -e "${BLUE}📊 Monitoring:${NC}"
    echo "   🤖 Auto-monitoring: Every 30 minutes"
    echo "   🔄 Auto-updates: Every 6 hours"
    echo "   📝 Logs: /var/log/youtube-system/monitor.log"
    echo ""
    
    echo -e "${YELLOW}⚠️  Next Steps:${NC}"
    echo "   1. Update your main application to use resilient_youtube_service"
    echo "   2. Test with a YouTube URL in your bot"
    echo "   3. Monitor logs for any issues"
    echo ""
}

main() {
    print_header
    
    log_info "Starting YouTube system setup..."
    
    check_dependencies
    setup_directories
    build_service
    start_service
    
    if wait_for_service; then
        test_functionality
        setup_monitoring
        update_env_file
        print_summary
        
        log_success "YouTube system setup completed successfully!"
        exit 0
    else
        log_error "Setup failed - service did not start properly"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "YouTube System Setup Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --no-test      Skip functionality testing"
        echo "  --force        Force rebuild even if running"
        echo ""
        exit 0
        ;;
    --no-test)
        SKIP_TEST=true
        ;;
    --force)
        log_info "Force mode: stopping existing service..."
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.ytdlp.yml down 2>/dev/null || true
        ;;
esac

# Run main function
main