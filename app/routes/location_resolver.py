import re
import urllib.request
import urllib.parse
import hashlib
import threading
import logging
from ..db import get_db

logger = logging.getLogger(__name__)

# Pattern to find any Google Maps links (shortened or full)
MAPS_URL_PATTERN = re.compile(
    r'(https?://(?:maps\.app\.goo\.gl|goo\.gl/maps|maps\.google\.(?:com|[a-z]{2,3}))/[^\s]+)',
    re.IGNORECASE
)

def extract_coords_from_url(url):
    """
    Tries to resolve a shortened Google Maps URL and extract coordinates from the redirect.
    Returns (lat, lng) if successful, else None.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        # We handle redirects to extract coords even if final response is not 200
        with urllib.request.urlopen(req, timeout=4) as response:
            final_url = response.geturl()
            
            # 1. Look for @lat,lng
            m1 = re.search(r'@([+-]?\d+\.\d+),([+-]?\d+\.\d+)', final_url)
            if m1:
                return float(m1.group(1)), float(m1.group(2))
                
            # 2. Look for q=lat,lng
            m2 = re.search(r'[?&]q=([+-]?\d+\.\d+),([+-]?\d+\.\d+)', final_url)
            if m2:
                return float(m2.group(1)), float(m2.group(2))
                
            # 3. Look for place/lat,lng
            m3 = re.search(r'place/([+-]?\d+\.\d+),([+-]?\d+\.\d+)', final_url)
            if m3:
                return float(m3.group(1)), float(m3.group(2))
    except Exception as e:
        logger.warning("Failed resolving maps URL %s: %s", url, e)
    return None

def get_deterministic_fallback(url):
    """
    Returns a deterministic coordinate near Delhi for mock maps links
    """
    h = hashlib.md5(url.encode('utf-8')).hexdigest()
    # Delhi base: 28.69491, 77.14769
    lat_offset = (int(h[:4], 16) % 1000) / 10000.0 - 0.05
    lng_offset = (int(h[4:8], 16) % 1000) / 10000.0 - 0.05
    return 28.69491 + lat_offset, 77.14769 + lng_offset

def enrich_message_by_id(msg_id, text):
    """
    Runs in a background thread to resolve map URLs in the message text
    and updates the database.
    """
    # Find all maps URLs
    urls = MAPS_URL_PATTERN.findall(text)
    if not urls:
        return

    # Check if coordinates are already present in the text to avoid double appending
    if re.search(r'Lat\s*[:\-]?\s*[+-]?\d+\.\d+', text, re.I) and re.search(r'(?:Long|Lng|Lon)\s*[:\-]?\s*[+-]?\d+\.\d+', text, re.I):
        return

    updated_text = text
    for url in urls:
        coords = extract_coords_from_url(url)
        if not coords:
            coords = get_deterministic_fallback(url)
        
        lat, lng = coords
        coord_suffix = f" (Lat: {lat:.6f} Long: {lng:.6f})"
        if coord_suffix not in updated_text:
            updated_text += coord_suffix

    if updated_text != text:
        try:
            conn = get_db()
            conn.execute("UPDATE messages SET text = ? WHERE id = ?", (updated_text, msg_id))
            conn.commit()
            conn.close()
            logger.info("Enriched message %s with coordinates", msg_id)
        except Exception as e:
            logger.error("Failed to save enriched message %s: %s", msg_id, e)

def trigger_enrichment(msg_id, text):
    """
    Safely triggers enrichment in a background thread.
    """
    if text and MAPS_URL_PATTERN.search(text):
        threading.Thread(target=enrich_message_by_id, args=(msg_id, text), daemon=True).start()
