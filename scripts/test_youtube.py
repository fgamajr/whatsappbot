#!/usr/bin/env python3
"""
Script de teste para verificar se o sistema YouTube está funcionando
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.youtube_downloader import youtube_service
from app.utils.youtube_detector import detect_youtube_urls


async def test_dependencies():
    """Test if dependencies are installed"""
    try:
        import yt_dlp
        print("✅ yt-dlp imported successfully")
    except ImportError as e:
        print(f"❌ yt-dlp import failed: {e}")
        return False
    
    try:
        import ffmpeg
        print("✅ ffmpeg-python imported successfully")
    except ImportError as e:
        print(f"❌ ffmpeg-python import failed: {e}")
        return False
    
    return True


async def test_url_detection():
    """Test URL detection"""
    test_urls = [
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "Check this video: https://youtube.com/watch?v=dQw4w9WgXcQ amazing!",
        "Not a youtube link: https://google.com"
    ]
    
    print("\n🔍 Testing URL detection:")
    for test_text in test_urls:
        urls = detect_youtube_urls(test_text)
        print(f"Text: {test_text}")
        print(f"URLs found: {urls}")
        print()


async def test_video_info():
    """Test getting video info"""
    test_url = "https://youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - safe test
    
    print(f"🎬 Testing video info for: {test_url}")
    
    try:
        info = await youtube_service.get_video_info_only(test_url)
        print("✅ Video info retrieved successfully:")
        print(f"   Title: {info['title']}")
        print(f"   Duration: {info['duration_formatted']}")
        print(f"   Channel: {info['uploader']}")
        print(f"   Views: {info.get('view_count', 0):,}")
        return True
    except Exception as e:
        print(f"❌ Video info failed: {e}")
        return False


async def main():
    """Main test function"""
    print("🧪 YouTube System Tests\n")
    
    # Test 1: Dependencies
    if not await test_dependencies():
        print("\n❌ Dependency test failed. Install missing packages:")
        print("pip install yt-dlp==2024.12.3 ffmpeg-python==0.2.0")
        return
    
    # Test 2: URL Detection
    await test_url_detection()
    
    # Test 3: Video Info (requires internet)
    print("Testing video info (requires internet connection)...")
    await test_video_info()
    
    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())