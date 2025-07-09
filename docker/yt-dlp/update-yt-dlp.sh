#!/bin/bash

# Auto-update script for yt-dlp
set -e

echo "$(date): Checking for yt-dlp updates..."

# Get current version
CURRENT_VERSION=$(yt-dlp --version)
echo "Current version: $CURRENT_VERSION"

# Update yt-dlp
pip install --upgrade yt-dlp

# Get new version
NEW_VERSION=$(yt-dlp --version)
echo "New version: $NEW_VERSION"

if [ "$CURRENT_VERSION" != "$NEW_VERSION" ]; then
    echo "$(date): yt-dlp updated from $CURRENT_VERSION to $NEW_VERSION"
    
    # Test basic functionality
    if yt-dlp --version > /dev/null 2>&1; then
        echo "$(date): Update successful - yt-dlp is working"
        exit 0
    else
        echo "$(date): ERROR - yt-dlp update failed basic test"
        exit 1
    fi
else
    echo "$(date): No updates available"
    exit 0
fi