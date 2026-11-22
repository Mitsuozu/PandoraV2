"""External API: turn an address into map coordinates with OpenStreetMap's Nominatim service.

Nominatim's usage policy asks for an identifying User-Agent and at most one request per second;
Pandora only calls it when someone saves a changed address, so no extra rate limiting is needed.
On PythonAnywhere free accounts, urllib picks up the outbound proxy from the environment.
"""
import json
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'PandoraV2-inventory/1.0 (school project)'
SIX_PLACES = Decimal('0.000001')


def geocode(address):
    """Return (latitude, longitude) as Decimals, or None when not found or the service is unreachable."""
    address = (address or '').strip()
    if not address:
        return None
    url = f"{NOMINATIM_URL}?{urlencode({'q': address, 'format': 'jsonv2', 'limit': 1})}"
    try:
        with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=5) as response:
            results = json.load(response)
        return (Decimal(results[0]['lat']).quantize(SIX_PLACES),
                Decimal(results[0]['lon']).quantize(SIX_PLACES))
    except (OSError, ValueError, LookupError, ArithmeticError, TypeError):
        return None


def coordinates_for(address):
    """Field values for a Located model after its address changed (cleared when not found)."""
    found = geocode(address)
    return {'latitude': found[0], 'longitude': found[1]} if found else {'latitude': None, 'longitude': None}
