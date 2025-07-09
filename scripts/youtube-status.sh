#!/bin/bash

# YouTube Service Status Check Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 🎬 YouTube Service Status                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_docker_container() {
    echo -e "${BLUE}📦 Docker Container Status:${NC}"
    
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "yt-dlp-service"; then
        echo -e "${GREEN}✅ Container is running${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "yt-dlp-service"
    else
        echo -e "${RED}❌ Container is not running${NC}"
        
        # Check if container exists but is stopped
        if docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -q "yt-dlp-service"; then
            echo -e "${YELLOW}⚠️  Container exists but is stopped${NC}"
            docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep "yt-dlp-service"
        else
            echo -e "${RED}❌ Container does not exist${NC}"
        fi
        return 1
    fi
}

check_service_health() {
    echo -e "\n${BLUE}🏥 Service Health Check:${NC}"
    
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        HEALTH_RESPONSE=$(curl -s http://localhost:8080/health)
        echo -e "${GREEN}✅ Service is healthy${NC}"
        echo "Health Response: $HEALTH_RESPONSE"
    else
        echo -e "${RED}❌ Service health check failed${NC}"
        echo "Service may be starting up or experiencing issues"
        return 1
    fi
}

check_yt_dlp_version() {
    echo -e "\n${BLUE}📦 yt-dlp Version:${NC}"
    
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        VERSION_INFO=$(curl -s http://localhost:8080/health | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$VERSION_INFO" ]; then
            echo -e "${GREEN}✅ yt-dlp version: $VERSION_INFO${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not retrieve version info${NC}"
        fi
    else
        echo -e "${RED}❌ Cannot check version - service not responding${NC}"
        return 1
    fi
}

check_port_availability() {
    echo -e "\n${BLUE}🌐 Port Status:${NC}"
    
    if netstat -tlnp 2>/dev/null | grep -q ":8080 "; then
        echo -e "${GREEN}✅ Port 8080 is in use${NC}"
        PORT_INFO=$(netstat -tlnp 2>/dev/null | grep ":8080 " || echo "Port info not available")
        echo "$PORT_INFO"
    else
        echo -e "${RED}❌ Port 8080 is not in use${NC}"
        return 1
    fi
}

check_resource_usage() {
    echo -e "\n${BLUE}📊 Resource Usage:${NC}"
    
    if docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -q "yt-dlp-service"; then
        echo -e "${GREEN}✅ Resource usage:${NC}"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -1
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep "yt-dlp-service"
    else
        echo -e "${RED}❌ Cannot get resource usage - container not running${NC}"
        return 1
    fi
}

check_recent_logs() {
    echo -e "\n${BLUE}📋 Recent Logs (last 10 lines):${NC}"
    
    if docker logs yt-dlp-service --tail 10 2>/dev/null; then
        echo -e "${GREEN}✅ Logs retrieved${NC}"
    else
        echo -e "${RED}❌ Cannot retrieve logs${NC}"
        return 1
    fi
}

check_monitoring() {
    echo -e "\n${BLUE}🤖 Monitoring Status:${NC}"
    
    # Check if monitoring cron job exists
    if crontab -l 2>/dev/null | grep -q "youtube-monitor"; then
        echo -e "${GREEN}✅ Monitoring cron job is active${NC}"
        crontab -l | grep "youtube-monitor"
    else
        echo -e "${YELLOW}⚠️  Monitoring cron job not found${NC}"
    fi
    
    # Check monitoring logs
    if [ -f "/var/log/youtube-system/monitor.log" ]; then
        echo -e "${GREEN}✅ Monitoring log exists${NC}"
        echo "Recent monitoring entries:"
        tail -5 /var/log/youtube-system/monitor.log 2>/dev/null || echo "Cannot read log file"
    else
        echo -e "${YELLOW}⚠️  Monitoring log not found${NC}"
    fi
}

test_download() {
    echo -e "\n${BLUE}🧪 Quick Download Test:${NC}"
    
    if [ "${1:-}" = "--with-test" ]; then
        echo "Testing download functionality..."
        
        TEST_RESPONSE=$(curl -s -X POST http://localhost:8080/download \
            -H "Content-Type: application/json" \
            -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "max_file_size": 1048576}' \
            --max-time 30)
        
        if echo "$TEST_RESPONSE" | grep -q '"success"'; then
            echo -e "${GREEN}✅ Download test completed${NC}"
            echo "Response preview: $(echo "$TEST_RESPONSE" | head -c 200)..."
        else
            echo -e "${RED}❌ Download test failed${NC}"
            echo "Response: $TEST_RESPONSE"
        fi
    else
        echo -e "${YELLOW}ℹ️  Use --with-test to run download test${NC}"
    fi
}

print_summary() {
    echo -e "\n${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                      📊 Summary                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    local all_good=true
    
    # Container check
    if docker ps | grep -q "yt-dlp-service"; then
        echo -e "${GREEN}✅ Container: Running${NC}"
    else
        echo -e "${RED}❌ Container: Not Running${NC}"
        all_good=false
    fi
    
    # Health check
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Health: OK${NC}"
    else
        echo -e "${RED}❌ Health: Failed${NC}"
        all_good=false
    fi
    
    # Port check
    if netstat -tlnp 2>/dev/null | grep -q ":8080 "; then
        echo -e "${GREEN}✅ Port 8080: Available${NC}"
    else
        echo -e "${RED}❌ Port 8080: Not Available${NC}"
        all_good=false
    fi
    
    if [ "$all_good" = true ]; then
        echo -e "\n${GREEN}🎉 YouTube service is fully operational!${NC}"
    else
        echo -e "\n${RED}⚠️  YouTube service has issues - check details above${NC}"
        echo -e "${YELLOW}💡 Try: ./scripts/youtube-restart.sh${NC}"
    fi
}

print_quick_commands() {
    echo -e "\n${BLUE}🔧 Quick Commands:${NC}"
    echo "  ./scripts/youtube-restart.sh   - Restart service"
    echo "  ./scripts/youtube-logs.sh      - View detailed logs"
    echo "  ./scripts/youtube-update.sh    - Update yt-dlp"
    echo "  ./scripts/youtube-test.sh       - Run download test"
    echo ""
}

main() {
    print_header
    
    local exit_code=0
    
    check_docker_container || exit_code=1
    check_service_health || exit_code=1
    check_yt_dlp_version || exit_code=1
    check_port_availability || exit_code=1
    check_resource_usage || exit_code=1
    check_recent_logs || exit_code=1
    check_monitoring || exit_code=1
    test_download "$1"
    
    print_summary
    print_quick_commands
    
    exit $exit_code
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Status Check Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h      Show this help message"
        echo "  --with-test     Include download functionality test"
        echo "  --summary       Show only summary information"
        echo ""
        exit 0
        ;;
    --summary)
        print_header
        print_summary
        exit 0
        ;;
esac

# Run main function
main "$@"