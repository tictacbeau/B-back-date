import re
from email import message_from_file
from email.utils import parsedate_to_datetime
import datetime

# Try importing dateutil.parser since it is installed with pandas
try:
    from dateutil import parser as dateutil_parser
except ImportError:
    dateutil_parser = None

def parse_date_string(date_str):
    """
    Attempts to parse a date string into a datetime object.
    Returns timezone-naive datetime (local or converted) for easier date math.
    """
    if not date_str:
        return None
    date_str = date_str.strip()
    
    # Try RFC 2822 parser first (standard for email headers)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt:
            # Convert to timezone naive
            return dt.replace(tzinfo=None)
    except Exception:
        pass
        
    # Try dateutil parser (handles a wide variety of formats)
    if dateutil_parser:
        try:
            dt = dateutil_parser.parse(date_str)
            if dt:
                return dt.replace(tzinfo=None)
        except Exception:
            pass

    # Try common strptime formats as fallbacks
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y %H:%M:%S",
        "%d %b %Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    return None

def extract_date_from_eml(file_path):
    """
    Loads an .eml file and extracts the RFC 2822 "Date" header.
    Returns a datetime object (timezone naive) or None if parsing fails.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            msg = message_from_file(f)
        date_header = msg.get('Date')
        if date_header:
            return parse_date_string(date_header)
    except Exception as e:
        print(f"Error reading EML file {file_path}: {e}")
    return None

def extract_date_from_text(text):
    """
    Searches for a line starting with "Date: " (case-insensitive) and parses the datetime.
    Returns a datetime object (timezone naive) or None if not found or parsing fails.
    """
    if not text:
        return None
        
    # Search for a line starting with "Date: "
    # Supports multiline mode where ^ matches start of line
    pattern = r'^(?:Date|date):\s*(.*?)$'
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    if match:
        date_str = match.group(1).strip()
        # Clean up any trailing details like "(UTC)" or timezone names that might confuse parsers
        # e.g., "Mon, 1 Jun 2026 10:33:48 -0700 (PDT)" -> remove "(PDT)" if dateutil struggles,
        # but dateutil generally handles it. Let's try parsing directly first.
        parsed = parse_date_string(date_str)
        if parsed:
            return parsed
            
        # Clean up parentheses comments at the end if parsing failed
        # e.g. "Mon, 1 Jun 2026 10:33:48 -0700 (PDT)" -> "Mon, 1 Jun 2026 10:33:48 -0700"
        cleaned_str = re.sub(r'\s*\([^)]*\)\s*$', '', date_str)
        parsed = parse_date_string(cleaned_str)
        if parsed:
            return parsed

    return None
