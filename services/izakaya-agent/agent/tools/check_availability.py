"""
Restaurant availability check tool
"""
import json
import logging
import time

import requests
from strands import tool
from typing import Dict, Any
from utils.secrets import get_api_keys

logger = logging.getLogger(__name__)

def _log(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}, ensure_ascii=False, default=str))


@tool
def check_availability(place_id: str) -> Dict[str, Any]:
    """
    Check restaurant opening hours using Google Places API

    Args:
        place_id: Google Places Place ID

    Returns:
        Opening status (open_now, opening_hours)
    """
    t0 = time.time()
    api_keys = get_api_keys()
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "key": api_keys["google_places"],
        "place_id": place_id,
        "fields": "opening_hours",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        result = data.get("result", {})
        opening_hours = result.get("opening_hours", {})

        duration_ms = round((time.time() - t0) * 1000)
        open_now = opening_hours.get("open_now", False)
        _log("check_availability_ok", place_id=place_id, open_now=open_now, duration_ms=duration_ms)

        return {
            "open_now": open_now,
            "weekday_text": opening_hours.get("weekday_text", []),
        }
    except Exception as e:
        duration_ms = round((time.time() - t0) * 1000)
        _log("check_availability_error", place_id=place_id, error=type(e).__name__, duration_ms=duration_ms)
        return {
            "open_now": False,
            "weekday_text": [],
            "error": "営業時間を取得できませんでした",
        }
