#!/usr/bin/env python3
"""
Test script to verify YouTube logging functionality
"""

import asyncio
import sys
from pathlib import Path
import os

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.youtube_downloader import youtube_service


async def test_youtube_logging():
    """Test YouTube logging functionality"""
    print("🧪 Testing YouTube logging functionality...")
    
    # Test video info (this will generate logs)
    test_url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        print(f"📹 Getting video info for: {test_url}")
        info = await youtube_service.get_video_info_only(test_url)
        print(f"✅ Video info retrieved: {info['title']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Check if log file was created
    log_file = Path("logs/youtube_downloader.log")
    if log_file.exists():
        print(f"✅ Log file created: {log_file}")
        
        # Show log file size
        size = log_file.stat().st_size
        print(f"📊 Log file size: {size} bytes")
        
        # Show last few lines of log
        print("\n📋 Last 5 lines of log file:")
        print("-" * 60)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-5:]:
                print(line.strip())
        print("-" * 60)
        
    else:
        print("❌ Log file not found!")
    
    print("\n🎉 Logging test completed!")


if __name__ == "__main__":
    asyncio.run(test_youtube_logging())