import re
from typing import Optional, List
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


class YouTubeURLDetector:
    """Utility for detecting and extracting YouTube URLs from text"""
    
    # Comprehensive regex patterns for YouTube URLs
    YOUTUBE_PATTERNS = [
        # Standard YouTube URLs
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]+)',
        
        # YouTube short URLs
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]+)',
        
        # YouTube Shorts
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)',
        
        # YouTube mobile URLs
        r'(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        
        # YouTube embed URLs
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)',
        
        # YouTube playlist URLs (extract first video)
        r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
    ]
    
    @classmethod
    def detect_youtube_urls(cls, text: str) -> List[str]:
        """
        Detect all YouTube URLs in text
        
        Args:
            text: Text to search for YouTube URLs
            
        Returns:
            List of YouTube URLs found
        """
        urls = []
        
        try:
            # First, find all potential URLs in the text
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            potential_urls = re.findall(url_pattern, text)
            
            # Check each URL against YouTube patterns
            for url in potential_urls:
                if cls.is_youtube_url(url):
                    urls.append(url)
            
            # Also check for URLs without protocol
            for pattern in cls.YOUTUBE_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        video_id = match[0] if match[0] else match[1] if len(match) > 1 else None
                    else:
                        video_id = match
                    
                    if video_id:
                        # Reconstruct full URL
                        full_url = f"https://youtube.com/watch?v={video_id}"
                        if full_url not in urls:
                            urls.append(full_url)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in urls:
                video_id = cls.extract_video_id(url)
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    unique_urls.append(url)
            
            return unique_urls
            
        except Exception as e:
            logger.error("Error detecting YouTube URLs", extra={
                "error": str(e),
                "text_length": len(text)
            })
            return []
    
    @classmethod
    def is_youtube_url(cls, url: str) -> bool:
        """
        Check if URL is a valid YouTube URL
        
        Args:
            url: URL to check
            
        Returns:
            True if it's a YouTube URL
        """
        try:
            parsed = urlparse(url.lower())
            
            # Check domain
            youtube_domains = [
                'youtube.com', 'www.youtube.com', 'm.youtube.com',
                'youtu.be', 'youtube-nocookie.com'
            ]
            
            if parsed.netloc not in youtube_domains:
                return False
            
            # Check if we can extract video ID
            video_id = cls.extract_video_id(url)
            return video_id is not None
            
        except Exception:
            return False
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID if found, None otherwise
        """
        try:
            # Try each pattern
            for pattern in cls.YOUTUBE_PATTERNS:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    video_id = match.group(1)
                    # Validate video ID format (11 characters, alphanumeric + _ -)
                    if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                        return video_id
            
            # Try URL parsing for standard YouTube URLs
            parsed = urlparse(url)
            if parsed.netloc in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
                query_params = parse_qs(parsed.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                        return video_id
            
            return None
            
        except Exception as e:
            logger.error("Error extracting video ID", extra={
                "error": str(e),
                "url": url
            })
            return None
    
    @classmethod
    def normalize_youtube_url(cls, url: str) -> Optional[str]:
        """
        Normalize YouTube URL to standard format
        
        Args:
            url: YouTube URL in any format
            
        Returns:
            Normalized URL or None if invalid
        """
        try:
            video_id = cls.extract_video_id(url)
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
            return None
            
        except Exception as e:
            logger.error("Error normalizing YouTube URL", extra={
                "error": str(e),
                "url": url
            })
            return None
    
    @classmethod
    def extract_urls_with_context(cls, text: str) -> List[dict]:
        """
        Extract YouTube URLs with surrounding context
        
        Args:
            text: Text to search
            
        Returns:
            List of dicts with url, video_id, and context
        """
        results = []
        
        try:
            urls = cls.detect_youtube_urls(text)
            
            for url in urls:
                video_id = cls.extract_video_id(url)
                if video_id:
                    # Find context around the URL
                    url_start = text.find(url)
                    context_start = max(0, url_start - 50)
                    context_end = min(len(text), url_start + len(url) + 50)
                    context = text[context_start:context_end].strip()
                    
                    results.append({
                        'url': url,
                        'normalized_url': cls.normalize_youtube_url(url),
                        'video_id': video_id,
                        'context': context,
                        'position': url_start
                    })
            
            return results
            
        except Exception as e:
            logger.error("Error extracting URLs with context", extra={
                "error": str(e),
                "text_length": len(text)
            })
            return []


# Convenience functions for quick access
def detect_youtube_urls(text: str) -> List[str]:
    """Quick function to detect YouTube URLs in text"""
    return YouTubeURLDetector.detect_youtube_urls(text)


def is_youtube_url(url: str) -> bool:
    """Quick function to check if URL is YouTube"""
    return YouTubeURLDetector.is_youtube_url(url)


def extract_video_id(url: str) -> Optional[str]:
    """Quick function to extract video ID"""
    return YouTubeURLDetector.extract_video_id(url)


def normalize_youtube_url(url: str) -> Optional[str]:
    """Quick function to normalize YouTube URL"""
    return YouTubeURLDetector.normalize_youtube_url(url)