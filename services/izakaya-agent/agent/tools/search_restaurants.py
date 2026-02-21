"""
Hybrid restaurant search tool (Hotpepper + Google Places)
"""
import json
import logging
import re
import time
import unicodedata
from typing import List, Dict, Optional

import requests
from strands import tool
from utils.secrets import get_api_keys

def _log(event: str, **kwargs):
    print(json.dumps({"event": event, **kwargs}, ensure_ascii=False, default=str))

logger = logging.getLogger(__name__)

# Module-level storage for structured restaurant data
_last_results: List[Dict] = []


def get_last_results() -> List[Dict]:
    """Return and consume the last search results (clears after read)."""
    global _last_results
    results = list(_last_results)
    _last_results = []
    return results


def clear_last_results() -> None:
    """Clear stored results to prevent stale data between requests."""
    global _last_results
    _last_results = []


def _radius_to_hotpepper_range(radius_m: int) -> int:
    """Convert radius in meters to Hotpepper range code (1-5)."""
    if radius_m <= 300:
        return 1
    elif radius_m <= 500:
        return 2
    elif radius_m <= 1000:
        return 3
    elif radius_m <= 2000:
        return 4
    else:
        return 5


def _normalize_name(name: str) -> str:
    """店名正規化: 全角→半角、空白除去、支店名除去"""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[\s　]+', '', name)
    name = re.sub(r'(店|支店|本店|駅前店)$', '', name)
    return name.lower()


def _fuzzy_match(name: str, candidates: List[Dict]) -> Optional[Dict]:
    """店名の部分一致・正規化マッチング"""
    normalized = _normalize_name(name)
    for c in candidates:
        if _normalize_name(c["name"]) == normalized:
            return c
    for c in candidates:
        cn = _normalize_name(c["name"])
        if normalized in cn or cn in normalized:
            return c
    return None


@tool
def search_restaurants(
    lat: float,
    lon: float,
    radius: int = 500,
    limit: int = 10,
    genre: str = "G001",
    budget_max: int = None,
    keyword: str = None,
) -> List[Dict]:
    """
    Search recommended restaurants using hybrid search

    Args:
        lat: Latitude
        lon: Longitude
        radius: Search radius in meters (default: 500)
        limit: Maximum number of results to return
        genre: Genre code (G001=居酒屋, G002=ダイニングバー, ..., G017=アジア・エスニック)
        budget_max: Maximum budget per person in yen
        keyword: Free text keyword for filtering (e.g., 個室, 飲み放題, デート, 日本酒)
    """
    global _last_results
    t_start = time.time()

    try:
        api_keys = get_api_keys()

        # 1. Call Hotpepper API
        t0 = time.time()
        hotpepper_results = search_hotpepper(lat, lon, radius, api_keys["hotpepper"], genre, budget_max, keyword)
        _log("hotpepper_search", count=len(hotpepper_results), duration_ms=round((time.time() - t0) * 1000))

        # 2. Call Google Places API
        t0 = time.time()
        google_results = search_google_places(lat, lon, radius, api_keys["google_places"], genre, budget_max, keyword)
        _log("google_places_search", count=len(google_results), duration_ms=round((time.time() - t0) * 1000))

        # 3. Merge and score
        merged = merge_and_score(hotpepper_results, google_results)

        # 4. Sort by score and return top N
        merged.sort(key=lambda x: x["score"], reverse=True)
        top_results = merged[:limit]

        # 5. Enrich top results with details (phone, website, photo, address)
        t0 = time.time()
        enriched = enrich_top_results(top_results, api_keys["google_places"])
        _log("enrich_results", count=len(enriched), duration_ms=round((time.time() - t0) * 1000))

        # 6. Store genre keyword in each result for structured response
        genre_keyword = get_genre_keyword(genre)
        for r in enriched:
            r["genre"] = genre_keyword

        _last_results = enriched

        total_ms = round((time.time() - t_start) * 1000)
        _log("search_restaurants_complete", total=len(enriched), genre=genre, budget_max=budget_max, total_ms=total_ms)

        return enriched

    except Exception as e:
        total_ms = round((time.time() - t_start) * 1000)
        _log("search_restaurants_error", error_type=type(e).__name__, error=str(e), total_ms=total_ms)
        raise


def get_budget_code(budget_max: int) -> str:
    """
    Get Hotpepper budget code from maximum budget

    Args:
        budget_max: Maximum budget per person in yen

    Returns:
        Budget code (B001-B012) or None
    """
    if budget_max <= 500:
        return "B001"
    elif budget_max <= 1000:
        return "B002"
    elif budget_max <= 1500:
        return "B003"
    elif budget_max <= 2000:
        return "B008"
    elif budget_max <= 3000:
        return "B004"
    elif budget_max <= 4000:
        return "B005"
    elif budget_max <= 5000:
        return "B006"
    elif budget_max <= 7000:
        return "B012"
    else:
        return None  # No upper limit


def search_hotpepper(lat: float, lon: float, radius: int, api_key: str, genre: str = "G001", budget_max: int = None, keyword: str = None) -> List[Dict]:
    """
    Search restaurants using Hotpepper Gourmet API

    Args:
        lat: Latitude
        lon: Longitude
        radius: Search radius in meters
        api_key: Hotpepper API key
        genre: Genre code (G001=居酒屋, G002=ダイニングバー, etc.)
        budget_max: Maximum budget per person in yen
        keyword: Free text keyword for filtering

    Returns:
        List of restaurant information
    """
    url = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
    params = {
        "key": api_key,
        "lat": lat,
        "lng": lon,
        "range": _radius_to_hotpepper_range(radius),
        "genre": genre,
        "format": "json",
        "count": 50,
    }

    # Add budget filter if specified
    if budget_max is not None:
        budget_code = get_budget_code(budget_max)
        if budget_code:
            params["budget"] = budget_code

    # Add keyword filter if specified
    if keyword:
        params["keyword"] = keyword

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        restaurants = []
        for shop in data.get("results", {}).get("shop", []):
            restaurants.append({
                "name": shop["name"],
                "source": "hotpepper",
                "address": shop["address"],
                "url": shop["urls"]["pc"],
                "budget": (shop.get("budget") or {}).get("average", "不明"),
                "features": {
                    "private_room": (shop.get("private_room") or {}).get("name", ""),
                    "wifi": (shop.get("wifi") or {}).get("name", ""),
                    "card": (shop.get("card") or {}).get("name", ""),
                    "smoking": (shop.get("non_smoking") or {}).get("name", ""),
                    "parking": (shop.get("parking") or {}).get("name", ""),
                    "course": (shop.get("course") or {}).get("name", ""),
                    "free_drink": (shop.get("free_drink") or {}).get("name", ""),
                    "free_food": (shop.get("free_food") or {}).get("name", ""),
                    "lunch": (shop.get("lunch") or {}).get("name", ""),
                },
                "catch": shop.get("catch", ""),
                "access": shop.get("access", ""),
                "photo_url": (shop.get("photo") or {}).get("pc", {}).get("l", ""),
            })
        return restaurants
    except requests.RequestException:
        logger.warning("Hotpepper API request failed")
        return []
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logger.warning("Hotpepper API response parse error: %s", e)
        return []


def get_genre_keyword(genre: str) -> str:
    """
    Get Japanese keyword from genre code

    Args:
        genre: Genre code (G001-G017)

    Returns:
        Japanese keyword for Google Places search
    """
    genre_keywords = {
        "G001": "居酒屋",
        "G002": "ダイニングバー・バル",
        "G003": "創作料理",
        "G004": "和食",
        "G005": "洋食",
        "G006": "イタリアン・フレンチ",
        "G007": "中華",
        "G008": "焼肉・ホルモン",
        "G009": "韓国料理",
        "G010": "各国料理",
        "G011": "カラオケ・パーティ",
        "G012": "バー・カクテル",
        "G013": "ラーメン",
        "G014": "カフェ・スイーツ",
        "G016": "お好み焼き・もんじゃ",
        "G017": "アジア・エスニック料理",
    }
    return genre_keywords.get(genre, "居酒屋")


def search_google_places(lat: float, lon: float, radius: int, api_key: str, genre: str = "G001", budget_max: int = None, keyword: str = None) -> List[Dict]:
    """
    Search restaurants using Google Places API

    Args:
        lat: Latitude
        lon: Longitude
        radius: Search radius in meters
        api_key: Google Places API key
        genre: Genre code (G001=居酒屋, G002=ダイニングバー, etc.)
        budget_max: Maximum budget per person in yen
        keyword: Free text keyword for filtering

    Returns:
        List of restaurant information
    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    search_keyword = get_genre_keyword(genre)
    if keyword:
        search_keyword = f"{search_keyword} {keyword}"
    params = {
        "key": api_key,
        "location": f"{lat},{lon}",
        "radius": radius,
        "type": "restaurant",
        "keyword": search_keyword,
    }

    # Add price level filter if budget is specified
    # price_level: 0 (free), 1 (inexpensive), 2 (moderate), 3 (expensive), 4 (very expensive)
    if budget_max is not None:
        if budget_max <= 2000:
            params["maxprice"] = 1  # Inexpensive
        elif budget_max <= 4000:
            params["maxprice"] = 2  # Moderate
        elif budget_max <= 7000:
            params["maxprice"] = 3  # Expensive

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Check Google Places API application-level status
        status = data.get("status", "")
        if status not in ("OK", "ZERO_RESULTS"):
            logger.warning("Google Places Nearby Search returned status: %s", status)
            return []

        restaurants = []
        for place in data.get("results", []):
            restaurant = {
                "name": place["name"],
                "source": "google",
                "rating": place.get("rating", 0),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "place_id": place["place_id"],
                "address": place.get("vicinity", ""),
                "price_level": place.get("price_level"),
                "open_now": place.get("opening_hours", {}).get("open_now"),
                "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}",
            }

            # Extract first photo reference
            photos = place.get("photos", [])
            if photos:
                restaurant["photo_reference"] = photos[0].get("photo_reference", "")

            restaurants.append(restaurant)
        return restaurants
    except requests.RequestException:
        logger.warning("Google Places API request failed")
        return []
    except (KeyError, ValueError, AttributeError, TypeError) as e:
        logger.warning("Google Places API response parse error: %s", e)
        return []


def merge_and_score(hotpepper: List[Dict], google: List[Dict]) -> List[Dict]:
    """
    Merge results from both APIs and calculate scores

    Scoring rules:
    - Listed in both: +10 points
    - Google rating × 20 points
    - Review count (normalized) × 10 points
    - Hotpepper-only: 30 points base

    Args:
        hotpepper: Hotpepper results
        google: Google Places results

    Returns:
        Merged and scored results
    """
    merged = []
    hp_matched = set()

    for g in google:
        score = (g.get("rating") or 0) * 20
        score += min((g.get("user_ratings_total") or 0) / 100, 1.0) * 10

        matched_hp = _fuzzy_match(g["name"], hotpepper)
        if matched_hp:
            score += 10
            g["budget"] = matched_hp.get("budget")
            g["hotpepper_url"] = matched_hp.get("url")
            g["features"] = matched_hp.get("features", {})
            g["catch"] = matched_hp.get("catch", "")
            g["access"] = matched_hp.get("access", "")
            if not g.get("photo_url") and matched_hp.get("photo_url"):
                g["photo_url"] = matched_hp["photo_url"]
            if not g.get("address") and matched_hp.get("address"):
                g["address"] = matched_hp["address"]
            hp_matched.add(matched_hp["name"])

        g["score"] = round(score, 1)
        merged.append(g)

    # Hotpepper-only の店舗を追加
    for hp in hotpepper:
        if hp["name"] not in hp_matched:
            hp["score"] = 30.0
            hp["source"] = "hotpepper_only"
            merged.append(hp)

    return merged


def enrich_top_results(results: List[Dict], api_key: str, max_detail_calls: int = 5) -> List[Dict]:
    """
    Enrich top results with Place Details (phone, website) and photo URLs.

    Only calls Place Details API for the top N results to minimize API costs.

    Args:
        results: Scored and sorted restaurant list
        api_key: Google Places API key
        max_detail_calls: Max number of Place Details API calls

    Returns:
        Enriched restaurant list
    """
    for i, r in enumerate(results):
        place_id = r.get("place_id")
        if not place_id:
            continue

        # Resolve photo URL server-side to avoid exposing API key to client
        photo_ref = r.pop("photo_reference", None)
        if photo_ref:
            photo_api_url = (
                f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth=400&photo_reference={photo_ref}&key={api_key}"
            )
            try:
                resp = requests.get(photo_api_url, allow_redirects=False, timeout=5)
                if resp.status_code in (301, 302) and "location" in resp.headers:
                    r["photo_url"] = resp.headers["location"]
            except Exception:
                pass  # Skip photo on error

        # Call Place Details for top results only
        if i < max_detail_calls:
            details = _fetch_place_details(place_id, api_key)
            if details:
                if not r.get("address") and details.get("formatted_address"):
                    r["address"] = details["formatted_address"]
                if details.get("formatted_phone_number"):
                    r["phone"] = details["formatted_phone_number"]
                if details.get("website"):
                    r["website"] = details["website"]
                if details.get("url"):
                    r["google_maps_url"] = details["url"]

        # Set primary URL: prefer Hotpepper, then website, then Google Maps
        r["url"] = r.get("hotpepper_url") or r.get("website") or r.get("google_maps_url", "")

    return results


def _fetch_place_details(place_id: str, api_key: str) -> Optional[Dict]:
    """
    Fetch additional details for a single place.

    Args:
        place_id: Google Places ID
        api_key: Google Places API key

    Returns:
        Place details dict or None on error
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "key": api_key,
        "place_id": place_id,
        "fields": "formatted_address,formatted_phone_number,website,url",
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Check application-level status
        status = data.get("status", "")
        if status != "OK":
            logger.warning("Place Details API returned status: %s for place_id: %s", status, place_id)
            return None

        return data.get("result", {})
    except requests.RequestException:
        logger.warning("Place Details API request failed for place_id: %s", place_id)
        return None
