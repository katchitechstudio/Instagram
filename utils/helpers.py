import re
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    if not text:
        return ""
    
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())
    text = text.strip()
    
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + suffix


def remove_html_tags(text: str) -> str:
    if not text:
        return ""
    
    clean = re.sub(r'<[^>]+>', '', text)
    
    clean = clean.replace("&nbsp;", " ")
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    
    return clean_text(clean)


def sanitize_filename(filename: str) -> str:
    if not filename:
        return "unnamed"
    
    safe = re.sub(r'[<>:"/\\|?*]', '', filename)
    safe = safe.replace(" ", "_")
    
    turkish_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    for turkish, english in turkish_map.items():
        safe = safe.replace(turkish, english)
    
    return safe.lower()
