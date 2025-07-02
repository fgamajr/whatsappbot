# Telegram Bot Setup Guide

## Prerequisites

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` command
   - Follow instructions to create your bot
   - Save the bot token (format: `123456789:ABCDEF...`)

## Configuration Steps

### 1. Environment Configuration

Add your Telegram bot token to `.env`:
```bash
# Copy example file
cp .env.example .env

# Edit .env and add your actual values:
TELEGRAM_BOT_TOKEN=<paste_your_bot_token_here>
DEFAULT_MESSAGING_PROVIDER=telegram  # Optional: to make Telegram default
```

### 2. Set Up Webhook

Use the provided setup script:
```bash
python3 scripts/setup_telegram.py YOUR_BOT_TOKEN https://yourdomain.com
```

**Example:**
```bash
python3 scripts/setup_telegram.py YOUR_BOT_TOKEN https://yourdomain.com
```

### 3. Manual Webhook Setup (Alternative)

If you prefer manual setup:
```bash
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://yourdomain.com/webhook/telegram"}'
```

## Testing

1. **Start your bot server**:
   ```bash
   python3 -m app.main
   ```

2. **Test with your bot**:
   - Find your bot on Telegram
   - Send `/start` or `help`
   - Send a voice message to test transcription

## Webhook Endpoints

- **WhatsApp**: `/webhook/whatsapp` (legacy endpoint)
- **Telegram**: `/webhook/telegram` (new endpoint)
- **Both work simultaneously**

## Bot Commands

- `help` or `/help` - Show help message
- `status` - Show system status
- Send voice/audio message - Trigger transcription and analysis

## Troubleshooting

### Check Webhook Status
```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getWebhookInfo"
```

### Common Issues

1. **Invalid token**: Double-check bot token from BotFather
2. **HTTPS required**: Telegram webhooks require HTTPS
3. **Port issues**: Make sure your server is accessible on the configured port
4. **Firewall**: Ensure webhook URL is publicly accessible

### Logs

Check application logs for webhook activity:
```bash
# If using Docker
docker logs your_container_name

# If running directly
tail -f logs/app.log
```

## Multiple Providers

You can run both WhatsApp and Telegram simultaneously:

1. Keep existing WhatsApp configuration
2. Add Telegram configuration
3. Both services will work independently
4. Users can interact with either platform

## Environment Variables

```bash
# Required for Telegram
TELEGRAM_BOT_TOKEN=<your_actual_bot_token>

# Optional: Set default provider
DEFAULT_MESSAGING_PROVIDER=telegram  # or "whatsapp"

# WhatsApp settings (keep existing if using WhatsApp)
WHATSAPP_TOKEN=<your_actual_token>
WHATSAPP_VERIFY_TOKEN=<your_actual_verify_token>
PHONE_NUMBER_ID=<your_actual_phone_id>
```