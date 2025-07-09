#!/bin/bash

# YouTube Service Test Script
# Comprehensive testing of YouTube download functionality

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test URLs
TEST_URLS=(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - reliable test video
    "https://youtu.be/dQw4w9WgXcQ"                # Short format
    "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # Me at the zoo - first YouTube video
)

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
    echo "║                  🧪 YouTube Service Test                     ║"
    echo "║                  Comprehensive Testing                       ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_service_health() {
    log_info "Checking service health..."
    
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        local health_response=$(curl -s http://localhost:8080/health)
        log_success "Service is healthy"
        echo "Health Response: $health_response"
        return 0
    else
        log_error "Service health check failed"
        echo "Make sure the service is running: ./scripts/youtube-start.sh"
        return 1
    fi
}

test_health_endpoint() {
    echo -e "\n${BLUE}🏥 Testing Health Endpoint:${NC}"
    
    local response=$(curl -s -w "HTTP_CODE:%{http_code}" http://localhost:8080/health)
    local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$http_code" = "200" ]; then
        log_success "Health endpoint test passed"
        echo "Response: $body"
        return 0
    else
        log_error "Health endpoint test failed (HTTP $http_code)"
        echo "Response: $body"
        return 1
    fi
}

test_info_extraction() {
    local url="$1"
    
    echo -e "\n${BLUE}ℹ️  Testing Info Extraction for: $url${NC}"
    
    # Test with minimal download to just get info
    local test_data='{
        "url": "'$url'",
        "max_file_size": 1024,
        "max_duration": 10
    }'
    
    local response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -X POST http://localhost:8080/download \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        --max-time 30)
    
    local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$http_code" = "200" ]; then
        local success=$(echo "$body" | grep -o '"success":[^,]*' | cut -d: -f2)
        
        if [ "$success" = "true" ]; then
            log_success "Info extraction successful"
            
            # Extract metadata
            local title=$(echo "$body" | grep -o '"title":"[^"]*"' | cut -d'"' -f4)
            local duration=$(echo "$body" | grep -o '"duration":[^,]*' | cut -d: -f2)
            local uploader=$(echo "$body" | grep -o '"uploader":"[^"]*"' | cut -d'"' -f4)
            
            echo "  Title: $title"
            echo "  Duration: ${duration}s"
            echo "  Uploader: $uploader"
            
            return 0
        else
            local error=$(echo "$body" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
            log_warning "Info extraction failed: $error"
            return 1
        fi
    else
        log_error "HTTP error $http_code"
        echo "Response: $body"
        return 1
    fi
}

test_small_download() {
    local url="$1"
    
    echo -e "\n${BLUE}📥 Testing Small Download for: $url${NC}"
    
    # Test with small file size limit
    local test_data='{
        "url": "'$url'",
        "max_file_size": 5242880,
        "max_duration": 60,
        "quality": "worst"
    }'
    
    log_info "Starting download test (may take 30-60 seconds)..."
    
    local response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -X POST http://localhost:8080/download \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        --max-time 120)
    
    local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$http_code" = "200" ]; then
        local success=$(echo "$body" | grep -o '"success":[^,]*' | cut -d: -f2)
        
        if [ "$success" = "true" ]; then
            log_success "Download test successful"
            
            # Extract file info
            local file_size=$(echo "$body" | grep -o '"file_size":[^,]*' | cut -d: -f2)
            local is_audio=$(echo "$body" | grep -o '"is_audio_only":[^,]*' | cut -d: -f2)
            
            echo "  File size: $file_size bytes ($(( file_size / 1024 ))KB)"
            echo "  Audio only: $is_audio"
            
            return 0
        else
            local error=$(echo "$body" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
            log_warning "Download test failed: $error"
            return 1
        fi
    else
        log_error "HTTP error $http_code"
        echo "Response: $body"
        return 1
    fi
}

test_update_endpoint() {
    echo -e "\n${BLUE}🔄 Testing Update Endpoint:${NC}"
    
    local response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -X POST http://localhost:8080/update \
        --max-time 60)
    
    local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$http_code" = "200" ]; then
        log_success "Update endpoint test passed"
        
        local success=$(echo "$body" | grep -o '"success":[^,]*' | cut -d: -f2)
        local old_version=$(echo "$body" | grep -o '"old_version":"[^"]*"' | cut -d'"' -f4)
        local new_version=$(echo "$body" | grep -o '"new_version":"[^"]*"' | cut -d'"' -f4)
        local message=$(echo "$body" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
        
        echo "  Success: $success"
        echo "  Old version: $old_version"
        echo "  New version: $new_version"
        echo "  Message: $message"
        
        return 0
    else
        log_error "Update endpoint test failed (HTTP $http_code)"
        echo "Response: $body"
        return 1
    fi
}

test_error_handling() {
    echo -e "\n${BLUE}❌ Testing Error Handling:${NC}"
    
    # Test with invalid URL
    log_info "Testing invalid URL handling..."
    
    local test_data='{
        "url": "https://invalid-youtube-url.com/watch?v=invalid",
        "max_file_size": 1048576
    }'
    
    local response=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -X POST http://localhost:8080/download \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        --max-time 30)
    
    local http_code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
    local body=$(echo "$response" | sed 's/HTTP_CODE:[0-9]*$//')
    
    if [ "$http_code" = "200" ]; then
        local success=$(echo "$body" | grep -o '"success":[^,]*' | cut -d: -f2)
        
        if [ "$success" = "false" ]; then
            log_success "Error handling test passed (correctly rejected invalid URL)"
            local error=$(echo "$body" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
            echo "  Error message: $error"
            return 0
        else
            log_warning "Error handling test failed (should have rejected invalid URL)"
            return 1
        fi
    else
        log_error "HTTP error $http_code"
        return 1
    fi
}

test_performance() {
    echo -e "\n${BLUE}⚡ Testing Performance:${NC}"
    
    # Test response time for health check
    log_info "Testing health check response time..."
    
    local start_time=$(date +%s%N)
    curl -f -s http://localhost:8080/health > /dev/null 2>&1
    local end_time=$(date +%s%N)
    
    local response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
    
    echo "  Health check response time: ${response_time}ms"
    
    if [ "$response_time" -lt 1000 ]; then
        log_success "Performance test passed (response time < 1s)"
    else
        log_warning "Performance test warning (response time > 1s)"
    fi
}

run_comprehensive_test() {
    local url="${1:-${TEST_URLS[0]}}"
    
    echo -e "\n${BLUE}🎯 Running Comprehensive Test for: $url${NC}"
    
    local tests_passed=0
    local tests_total=4
    
    # Test 1: Health check
    if check_service_health; then
        tests_passed=$((tests_passed + 1))
    fi
    
    # Test 2: Info extraction
    if test_info_extraction "$url"; then
        tests_passed=$((tests_passed + 1))
    fi
    
    # Test 3: Small download
    if test_small_download "$url"; then
        tests_passed=$((tests_passed + 1))
    fi
    
    # Test 4: Update endpoint
    if test_update_endpoint; then
        tests_passed=$((tests_passed + 1))
    fi
    
    echo -e "\n${BLUE}📊 Test Results: $tests_passed/$tests_total tests passed${NC}"
    
    if [ "$tests_passed" -eq "$tests_total" ]; then
        log_success "All tests passed!"
        return 0
    else
        log_warning "Some tests failed"
        return 1
    fi
}

main() {
    local test_type="${1:-comprehensive}"
    local test_url="${2:-${TEST_URLS[0]}}"
    
    print_header
    
    case "$test_type" in
        health)
            test_health_endpoint
            ;;
        info)
            test_info_extraction "$test_url"
            ;;
        download)
            test_small_download "$test_url"
            ;;
        update)
            test_update_endpoint
            ;;
        error)
            test_error_handling
            ;;
        performance|perf)
            test_performance
            ;;
        comprehensive|all)
            if ! check_service_health; then
                exit 1
            fi
            
            test_health_endpoint
            test_performance
            test_error_handling
            
            log_info "Testing with multiple URLs..."
            local all_passed=true
            
            for url in "${TEST_URLS[@]}"; do
                if ! run_comprehensive_test "$url"; then
                    all_passed=false
                fi
            done
            
            echo -e "\n${BLUE}"
            echo "╔══════════════════════════════════════════════════════════════╗"
            echo "║                     🏁 Final Results                        ║"
            echo "╚══════════════════════════════════════════════════════════════╝"
            echo -e "${NC}"
            
            if [ "$all_passed" = true ]; then
                log_success "All comprehensive tests passed!"
                echo -e "${GREEN}🎉 YouTube service is fully functional!${NC}"
                exit 0
            else
                log_warning "Some comprehensive tests failed"
                echo -e "${YELLOW}⚠️  YouTube service has issues - check details above${NC}"
                exit 1
            fi
            ;;
        *)
            # Treat as URL if it starts with http
            if [[ "$test_type" =~ ^https?:// ]]; then
                run_comprehensive_test "$test_type"
            else
                log_error "Unknown test type: $test_type"
                exit 1
            fi
            ;;
    esac
}

# Handle help
case "${1:-}" in
    --help|-h|help)
        echo "YouTube Service Test Script"
        echo ""
        echo "Usage: $0 [TEST_TYPE] [URL]"
        echo ""
        echo "Test Types:"
        echo "  comprehensive, all  Run all tests (default)"
        echo "  health              Test health endpoint only"
        echo "  info                Test video info extraction"
        echo "  download            Test small download"
        echo "  update              Test update endpoint"
        echo "  error               Test error handling"
        echo "  performance, perf   Test performance/response times"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Run all tests"
        echo "  $0 health                            # Test health only"
        echo "  $0 download                          # Test download with default URL"
        echo "  $0 info \"https://youtu.be/dQw4w9WgXcQ\"  # Test info extraction with custom URL"
        echo "  $0 \"https://youtu.be/jNQXAC9IVRw\"      # Run comprehensive test with custom URL"
        echo ""
        echo "Note: Tests use small file size limits to avoid long downloads"
        echo ""
        exit 0
        ;;
esac

# Run main function
main "$@"