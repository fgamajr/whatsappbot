#!/bin/bash

# Deploy yt-dlp service with monitoring
set -e

echo "🚀 Deploying yt-dlp service..."

# Build and start the service
docker-compose -f docker-compose.ytdlp.yml build
docker-compose -f docker-compose.ytdlp.yml up -d

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
sleep 10

# Health check
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        echo "✅ Service is healthy!"
        break
    else
        echo "⏳ Service not ready yet... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 5
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Service failed to start properly"
    docker-compose -f docker-compose.ytdlp.yml logs
    exit 1
fi

# Test download functionality
echo "🧪 Testing download functionality..."
TEST_URL="https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing

curl -X POST http://localhost:8080/download \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$TEST_URL\"}" \
  > /tmp/test_response.json

if grep -q '"success": true' /tmp/test_response.json; then
    echo "✅ Download test successful!"
else
    echo "❌ Download test failed"
    cat /tmp/test_response.json
    exit 1
fi

# Set up monitoring cron job
echo "📊 Setting up monitoring..."
cat > /tmp/ytdlp-monitor.sh << 'EOF'
#!/bin/bash
# Monitor yt-dlp service and auto-update

LOG_FILE="/var/log/ytdlp-monitor.log"
SERVICE_URL="http://localhost:8080"

log_message() {
    echo "$(date): $1" >> "$LOG_FILE"
}

# Health check
if ! curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
    log_message "ERROR: Service health check failed"
    # Restart service
    docker-compose -f /path/to/docker-compose.ytdlp.yml restart yt-dlp-service
    exit 1
fi

# Auto-update check
RESPONSE=$(curl -s -X POST "$SERVICE_URL/update")
if echo "$RESPONSE" | grep -q '"success": true'; then
    log_message "INFO: Service update check completed"
else
    log_message "WARNING: Service update check failed"
fi

log_message "INFO: Health check passed"
EOF

chmod +x /tmp/ytdlp-monitor.sh
sudo mv /tmp/ytdlp-monitor.sh /usr/local/bin/

# Add to crontab if not exists
if ! crontab -l | grep -q "ytdlp-monitor"; then
    (crontab -l ; echo "*/30 * * * * /usr/local/bin/ytdlp-monitor.sh") | crontab -
    echo "✅ Monitoring cron job installed"
fi

echo "🎉 yt-dlp service deployed successfully!"
echo "📍 Service URL: http://localhost:8080"
echo "🔍 Health check: curl http://localhost:8080/health"
echo "🔄 Manual update: curl -X POST http://localhost:8080/update"