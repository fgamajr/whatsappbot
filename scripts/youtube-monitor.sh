#!/bin/bash

# YouTube Service Monitor Script
# Continuous monitoring with dashboard-style output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REFRESH_INTERVAL=5
MAX_LOG_LINES=10

print_header() {
    clear
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 📊 YouTube Service Monitor                   ║"
    echo "║              Real-time Service Dashboard                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Press Ctrl+C to exit | Refresh: ${REFRESH_INTERVAL}s"
    echo ""
}

get_container_status() {
    if docker ps --format "{{.Names}}" | grep -q "yt-dlp-service"; then
        local status=$(docker ps --format "{{.Status}}" | grep -A1 "yt-dlp-service" | tail -1)
        echo -e "${GREEN}✅ Running${NC} ($status)"
    elif docker ps -a --format "{{.Names}}" | grep -q "yt-dlp-service"; then
        echo -e "${RED}❌ Stopped${NC}"
    else
        echo -e "${RED}❌ Not Found${NC}"
    fi
}

get_health_status() {
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        local response=$(curl -s http://localhost:8080/health)
        local version=$(echo "$response" | grep -o '"yt_dlp_version":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✅ Healthy${NC} (v$version)"
    else
        echo -e "${RED}❌ Unhealthy${NC}"
    fi
}

get_resource_usage() {
    if docker stats --no-stream --format "{{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -q "yt-dlp-service"; then
        docker stats --no-stream --format "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep -A1 "CPU" | tail -1
    else
        echo -e "${RED}N/A${NC}"
    fi
}

get_port_status() {
    if netstat -tlnp 2>/dev/null | grep -q ":8080 "; then
        echo -e "${GREEN}✅ Open${NC}"
    else
        echo -e "${RED}❌ Closed${NC}"
    fi
}

get_recent_logs() {
    if docker logs yt-dlp-service --tail $MAX_LOG_LINES 2>/dev/null | grep -v "^$"; then
        return 0
    else
        echo -e "${RED}No logs available${NC}"
        return 1
    fi
}

get_monitoring_status() {
    if crontab -l 2>/dev/null | grep -q "youtube-monitor"; then
        echo -e "${GREEN}✅ Active${NC}"
    else
        echo -e "${YELLOW}⚠️  Not Scheduled${NC}"
    fi
}

get_last_update() {
    if [ -f "/tmp/youtube-last-update" ]; then
        local last_update=$(cat /tmp/youtube-last-update)
        local current_time=$(date +%s)
        local diff=$((current_time - last_update))
        local hours=$((diff / 3600))
        
        if [ $hours -lt 1 ]; then
            local minutes=$((diff / 60))
            echo "${minutes}m ago"
        else
            echo "${hours}h ago"
        fi
    else
        echo "Never"
    fi
}

test_download_quick() {
    local test_result=$(curl -s -X POST http://localhost:8080/download \
        -H "Content-Type: application/json" \
        -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "max_file_size": 1024}' \
        --max-time 10 2>/dev/null)
    
    if echo "$test_result" | grep -q '"success"'; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ Failed${NC}"
    fi
}

display_dashboard() {
    print_header
    
    # Service Status Section
    echo -e "${CYAN}🔧 Service Status${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-20s %s\n" "Container:" "$(get_container_status)"
    printf "%-20s %s\n" "Health:" "$(get_health_status)"
    printf "%-20s %s\n" "Port 8080:" "$(get_port_status)"
    printf "%-20s %s\n" "Auto-Monitor:" "$(get_monitoring_status)"
    echo ""
    
    # Resource Usage Section
    echo -e "${CYAN}📊 Resource Usage${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if docker ps | grep -q "yt-dlp-service"; then
        echo "CPU\t\tMemory\t\tMem%"
        get_resource_usage
    else
        echo -e "${RED}Service not running${NC}"
    fi
    echo ""
    
    # Functionality Test
    echo -e "${CYAN}🧪 Quick Test${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-20s %s\n" "Download Test:" "$(test_download_quick)"
    printf "%-20s %s\n" "Last Update:" "$(get_last_update)"
    echo ""
    
    # Recent Logs Section
    echo -e "${CYAN}📋 Recent Logs (last $MAX_LOG_LINES lines)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    get_recent_logs | while IFS= read -r line; do
        # Colorize log levels
        line=$(echo "$line" | sed "s/ERROR/${RED}ERROR${NC}/g")
        line=$(echo "$line" | sed "s/WARN/${YELLOW}WARN${NC}/g")
        line=$(echo "$line" | sed "s/INFO/${GREEN}INFO${NC}/g")
        echo "$line"
    done | tail -$MAX_LOG_LINES
    echo ""
    
    # Footer
    echo -e "${BLUE}💡 Commands: status | logs | test | update | restart${NC}"
    echo -e "${BLUE}📅 $(date)${NC}"
}

monitor_loop() {
    while true; do
        display_dashboard
        sleep $REFRESH_INTERVAL
    done
}

single_check() {
    display_dashboard
}

monitor_with_alerts() {
    local last_status=""
    local alert_count=0
    
    while true; do
        local current_status="healthy"
        
        # Check container
        if ! docker ps | grep -q "yt-dlp-service"; then
            current_status="container_down"
        # Check health
        elif ! curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
            current_status="service_down"
        fi
        
        # Alert on status change
        if [ "$current_status" != "$last_status" ] && [ "$current_status" != "healthy" ]; then
            alert_count=$((alert_count + 1))
            echo -e "\n${RED}🚨 ALERT #$alert_count: $current_status at $(date)${NC}" | tee -a /var/log/youtube-system/alerts.log 2>/dev/null || true
            
            # Try auto-recovery
            if [ "$current_status" = "container_down" ]; then
                echo "Attempting auto-recovery: restarting container..."
                "$SCRIPT_DIR/youtube-restart.sh" > /dev/null 2>&1 || true
            fi
        elif [ "$current_status" = "healthy" ] && [ "$last_status" != "healthy" ] && [ -n "$last_status" ]; then
            echo -e "\n${GREEN}✅ RECOVERY: Service is healthy again at $(date)${NC}" | tee -a /var/log/youtube-system/alerts.log 2>/dev/null || true
        fi
        
        last_status="$current_status"
        
        display_dashboard
        sleep $REFRESH_INTERVAL
    done
}

main() {
    local mode="loop"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --once|-o)
                mode="once"
                shift
                ;;
            --alerts|-a)
                mode="alerts"
                shift
                ;;
            --interval=*)
                REFRESH_INTERVAL="${1#*=}"
                shift
                ;;
            --interval|-i)
                REFRESH_INTERVAL="$2"
                shift 2
                ;;
            --lines=*)
                MAX_LOG_LINES="${1#*=}"
                shift
                ;;
            --lines|-l)
                MAX_LOG_LINES="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Ensure monitoring directory exists
    mkdir -p /var/log/youtube-system 2>/dev/null || true
    
    case "$mode" in
        once)
            single_check
            ;;
        alerts)
            echo "Starting monitor with alerts and auto-recovery..."
            monitor_with_alerts
            ;;
        loop)
            monitor_loop
            ;;
    esac
}

# Handle help and signals
case "${1:-}" in
    --help|-h)
        echo "YouTube Service Monitor Script"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h         Show this help message"
        echo "  --once, -o         Run once and exit (no loop)"
        echo "  --alerts, -a       Monitor with alerts and auto-recovery"
        echo "  --interval=N, -i N Set refresh interval in seconds (default: 5)"
        echo "  --lines=N, -l N    Number of log lines to show (default: 10)"
        echo ""
        echo "Modes:"
        echo "  Default            Continuous dashboard display"
        echo "  --once             Single check and exit"
        echo "  --alerts           Continuous monitoring with alerts"
        echo ""
        echo "Examples:"
        echo "  $0                 # Start monitoring dashboard"
        echo "  $0 --once          # Single status check"
        echo "  $0 --alerts        # Monitor with auto-recovery"
        echo "  $0 -i 10           # Monitor with 10s refresh"
        echo ""
        exit 0
        ;;
esac

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Monitoring stopped${NC}"; exit 0' INT

main "$@"