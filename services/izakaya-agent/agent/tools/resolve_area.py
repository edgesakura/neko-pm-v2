"""
Area name to coordinates resolution tool with Google Geocoding API
"""
import json
import logging
import time

import requests
from strands import tool
from typing import Dict
from utils.secrets import get_api_keys

logger = logging.getLogger(__name__)

def _log(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}, ensure_ascii=False, default=str))


@tool
def resolve_area(area_name: str) -> Dict[str, float]:
    """
    Convert area name to latitude/longitude coordinates using Google Geocoding API

    Args:
        area_name: Area name (e.g., Shimbashi, Shibuya, Osaka, Fukuoka)

    Returns:
        Coordinate information (lat, lon, radius in meters)

    Raises:
        ValueError: If area name cannot be resolved
    """
    t0 = time.time()
    try:
        api_keys = get_api_keys()
        api_key = api_keys["google_places"]

        # Call Google Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{area_name}, Japan",
            "key": api_key,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Check API response status
        if data.get("status") != "OK":
            raise ValueError(f"Geocoding API error: {data.get('status')}")

        # Extract results
        results = data.get("results", [])
        if not results:
            raise ValueError(f"Area '{area_name}' not found")

        # Extract location from first result
        location = results[0]["geometry"]["location"]

        # Estimate search radius from viewport
        radius = 500  # default
        viewport = results[0]["geometry"].get("viewport", {})
        if viewport:
            ne = viewport.get("northeast", {})
            sw = viewport.get("southwest", {})
            if ne and sw:
                from math import radians, cos
                dlat = abs(ne["lat"] - sw["lat"])
                dlon = abs(ne["lng"] - sw["lng"])
                avg_lat = radians((ne["lat"] + sw["lat"]) / 2)
                km_lat = dlat * 111
                km_lon = dlon * 111 * cos(avg_lat)
                estimated_radius = int(max(km_lat, km_lon) * 500)
                radius = max(300, min(estimated_radius, 3000))

        duration_ms = round((time.time() - t0) * 1000)
        _log("resolve_area_ok", area=area_name, lat=location["lat"], lon=location["lng"], radius=radius, duration_ms=duration_ms)

        return {
            "lat": location["lat"],
            "lon": location["lng"],
            "radius": radius,
        }

    except ValueError:
        # Re-raise ValueError as-is
        raise
    except requests.RequestException as e:
        duration_ms = round((time.time() - t0) * 1000)
        _log("resolve_area_error", area=area_name, error="http", duration_ms=duration_ms)
        raise ValueError(f"Failed to resolve area '{area_name}'") from e
    except Exception as e:
        duration_ms = round((time.time() - t0) * 1000)
        _log("resolve_area_error", area=area_name, error=type(e).__name__, duration_ms=duration_ms)
        raise ValueError(f"Failed to resolve area '{area_name}'") from e
