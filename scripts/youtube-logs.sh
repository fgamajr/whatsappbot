#!/bin/bash

# YouTube Service Logs Script
# View and manage logs for the YouTube service

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
    echo "║                   📋 YouTube Service Logs                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_service_logs() {
    local lines="${1:-50}"
    local follow="${2:-false}"
    
    echo -e "${BLUE}📋 Service Container Logs:${NC}"
    
    if [ "$follow" = "true" ]; then
        echo "Following logs (Press Ctrl+C to stop)..."
        docker logs yt-dlp-service --tail "$lines" -f
    else
        docker logs yt-dlp-service --tail "$lines"
    fi
}

show_monitoring_logs() {
    local lines="${1:-20}"
    
    echo -e "\n${BLUE}🤖 Monitoring Logs:${NC}"
    
    if [ -f "/var/log/youtube-system/monitor.log" ]; then
        tail -n "$lines" /var/log/youtube-system/monitor.log
    else
        echo -e "${YELLOW}⚠️  Monitoring log file not found${NC}"
    fi
}

show_application_logs() {
    local lines="${1:-20}"
    
    echo -e "\n${BLUE}🎯 Application YouTube Logs:${NC}"
    
    if [ -f "$PROJECT_ROOT/logs/youtube_downloader.log" ]; then
        tail -n "$lines" "$PROJECT_ROOT/logs/youtube_downloader.log"
    else
        echo -e "${YELLOW}⚠️  Application YouTube log file not found${NC}"
    fi
}

show_docker_compose_logs() {
    local lines="${1:-30}"
    local follow="${2:-false}"
    
    echo -e "\n${BLUE}🐳 Docker Compose Logs:${NC}"
    
    cd "$PROJECT_ROOT"
    
    if [ "$follow" = "true" ]; then
        echo "Following logs (Press Ctrl+C to stop)..."
        docker-compose -f docker-compose.ytdlp.yml logs --tail="$lines" -f
    else
        docker-compose -f docker-compose.ytdlp.yml logs --tail="$lines"
    fi
}

show_system_logs() {
    echo -e "\n${BLUE}🖥️  System Logs (YouTube related):${NC}"
    
    # Show recent system logs related to Docker and the service
    if command -v journalctl &> /dev/null; then
        echo "Recent Docker/service related system logs:"
        journalctl -u docker --since "1 hour ago" --no-pager -n 10 2>/dev/null || echo "Cannot access system logs"
    else
        echo "journalctl not available"
    fi
}

analyze_logs() {
    echo -e "\n${BLUE}🔍 Log Analysis:${NC}"
    
    # Analyze service logs for common issues
    local logs=$(docker logs yt-dlp-service --tail 100 2>&1)
    
    # Check for errors
    local error_count=$(echo "$logs" | grep -ci "error" || echo "0")
    local warning_count=$(echo "$logs" | grep -ci "warning" || echo "0")
    
    echo "Error count (last 100 lines): $error_count"
    echo "Warning count (last 100 lines): $warning_count"
    
    if [ "$error_count" -gt 0 ]; then
        echo -e "\n${RED}Recent Errors:${NC}"
        echo "$logs" | grep -i "error" | tail -5
    fi
    
    if [ "$warning_count" -gt 0 ]; then
        echo -e "\n${YELLOW}Recent Warnings:${NC}"
        echo "$logs" | grep -i "warning" | tail -3
    fi
    
    # Check for specific issues
    if echo "$logs" | grep -qi "connection refused"; then
        echo -e "\n${RED}⚠️  Found connection issues${NC}"
    fi
    
    if echo "$logs" | grep -qi "timeout"; then
        echo -e "\n${YELLOW}⚠️  Found timeout issues${NC}"
    fi
    
    if echo "$logs" | grep -qi "youtube.*error"; then
        echo -e "\n${RED}⚠️  Found YouTube-specific errors${NC}"
    fi
}

export_logs() {
    local output_file="${1:-youtube-logs-$(date +%Y%m%d_%H%M%S).txt}"
    
    echo -e "${BLUE}📤 Exporting logs to: $output_file${NC}"
    
    {
        echo "YouTube Service Logs Export"
        echo "Generated: $(date)"
        echo "========================================"
        echo ""
        
        echo "=== SERVICE CONTAINER LOGS ==="
        docker logs yt-dlp-service --tail 200 2>&1
        echo ""
        
        echo "=== MONITORING LOGS ==="
        if [ -f "/var/log/youtube-system/monitor.log" ]; then
            tail -n 50 /var/log/youtube-system/monitor.log
        else
            echo "Monitor log not found"
        fi
        echo ""
        
        echo "=== APPLICATION LOGS ==="
        if [ -f "$PROJECT_ROOT/logs/youtube_downloader.log" ]; then
            tail -n 50 "$PROJECT_ROOT/logs/youtube_downloader.log"
        else
            echo "Application log not found"
        fi
        echo ""
        
        echo "=== DOCKER COMPOSE LOGS ==="
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.ytdlp.yml logs --tail=100 2>&1
        
    } > "$output_file"
    
    echo -e "${GREEN}✅ Logs exported to: $output_file${NC}"
}

clear_logs() {
    echo -e "${YELLOW}🗑️  Clearing logs...${NC}"
    
    # Clear Docker container logs
    docker logs yt-dlp-service --tail 1 > /dev/null 2>&1
    
    # Truncate monitoring logs
    if [ -f "/var/log/youtube-system/monitor.log" ]; then
        sudo truncate -s 0 /var/log/youtube-system/monitor.log 2>/dev/null || echo "Cannot clear monitoring logs (permission denied)"
    fi
    
    echo -e "${GREEN}✅ Logs cleared${NC}"
}

show_log_locations() {
    echo -e "${BLUE}📂 Log File Locations:${NC}"
    echo ""
    
    echo "Service Container Logs:"
    echo "  Command: docker logs yt-dlp-service"
    echo ""
    
    echo "Monitoring Logs:"
    if [ -f "/var/log/youtube-system/monitor.log" ]; then
        echo -e "  ${GREEN}✅${NC} /var/log/youtube-system/monitor.log"
        echo "  Size: $(du -h /var/log/youtube-system/monitor.log | cut -f1)"
    else
        echo -e "  ${RED}❌${NC} /var/log/youtube-system/monitor.log (not found)"
    fi
    echo ""
    
    echo "Application Logs:"
    if [ -f "$PROJECT_ROOT/logs/youtube_downloader.log" ]; then
        echo -e "  ${GREEN}✅${NC} $PROJECT_ROOT/logs/youtube_downloader.log"
        echo "  Size: $(du -h "$PROJECT_ROOT/logs/youtube_downloader.log" | cut -f1)"
    else
        echo -e "  ${RED}❌${NC} $PROJECT_ROOT/logs/youtube_downloader.log (not found)"
    fi
    echo ""
    
    echo "Docker Compose Logs:"
    echo "  Command: docker-compose -f docker-compose.ytdlp.yml logs"
}

main() {
    local command="${1:-show}"
    local lines="${2:-50}"
    local follow=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            show|view)
                command="show"
                shift
                ;;
            follow|-f|--follow)
                follow=true
                shift
                ;;
            analyze|analysis)
                command="analyze"
                shift
                ;;
            export)
                command="export"
                shift
                ;;
            clear|clean)
                command="clear"
                shift
                ;;
            locations|paths)
                command="locations"
                shift
                ;;
            monitoring|monitor)
                command="monitoring"
                shift
                ;;
            application|app)
                command="application"
                shift
                ;;
            system)
                command="system"
                shift
                ;;
            --lines=*)
                lines="${1#*=}"
                shift
                ;;
            --lines|-n)
                lines="$2"
                shift 2
                ;;
            *)
                if [[ "$1" =~ ^[0-9]+$ ]]; then
                    lines="$1"
                fi
                shift
                ;;
        esac
    done
    
    print_header
    
    case "$command" in
        show)
            show_service_logs "$lines" "$follow"
            if [ "$follow" = "false" ]; then
                show_monitoring_logs "10"
                show_application_logs "10"
            fi
            ;;
        analyze)
            analyze_logs
            ;;
        export)
            export_logs "$2"
            ;;
        clear)
            clear_logs
            ;;
        locations)
            show_log_locations
            ;;
        monitoring)
            show_monitoring_logs "$lines"
            ;;
        application)
            show_application_logs "$lines"
            ;;
        system)
            show_system_logs
            ;;
        docker)
            show_docker_compose_logs "$lines" "$follow"
            ;;
        *)
            echo "Unknown command: $command"
            exit 1
            ;;
    esac
}

# Handle help
case "${1:-}" in
    --help|-h|help)
        echo "YouTube Service Logs Script"
        echo ""
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  show, view          Show service logs (default)"
        echo "  follow, -f          Follow logs in real-time"
        echo "  analyze             Analyze logs for issues"
        echo "  export              Export all logs to file"
        echo "  clear, clean        Clear/truncate logs"
        echo "  locations, paths    Show log file locations"
        echo "  monitoring          Show only monitoring logs"
        echo "  application, app    Show only application logs"
        echo "  system              Show system logs"
        echo "  docker              Show docker-compose logs"
        echo ""
        echo "Options:"
        echo "  --lines=N, -n N     Number of lines to show (default: 50)"
        echo "  --follow, -f        Follow logs in real-time"
        echo ""
        echo "Examples:"
        echo "  $0                           # Show last 50 lines"
        echo "  $0 follow                    # Follow logs"
        echo "  $0 show 100                  # Show last 100 lines"
        echo "  $0 analyze                   # Analyze logs for issues"
        echo "  $0 export my-logs.txt        # Export logs to file"
        echo "  $0 monitoring                # Show monitoring logs only"
        echo ""
        exit 0
        ;;
esac

# Run main function
main "$@"