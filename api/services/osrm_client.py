import re
import requests

OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"
NOMINATIM_URL = "http://nominatim.openstreetmap.org/search"

COORD_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

METERS_TO_MILES = 0.000621371


class RouteResolutionError(Exception):
    """Raised when a location string can't be parsed or geocoded."""


def _try_parse_coordinates(location: str):
    match = COORD_PATTERN.match(location)
    if not match:
        return None
    lat, lng = float(match.group(1)), float(match.group(2))
    return lat, lng


def _geocode(location: str):
    response = requests.get(
        NOMINATIM_URL,
        params={"q": location, "format": "json", "limit": 1, "countrycodes": "us"},
        headers={"User-Agent": "fuel-route-api/1.0"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()

    if not results:
        raise RouteResolutionError(f"Could not geocode location: '{location}'")

    return float(results[0]["lat"]), float(results[0]["lon"])


def _resolve_location(location: str):
    coords = _try_parse_coordinates(location)
    if coords is not None:
        return coords
    return _geocode(location)


def get_route(start: str, finish: str) -> dict:
    start_lat, start_lng = _resolve_location(start)
    finish_lat, finish_lng = _resolve_location(finish)

    coordinates_params = f"{start_lng},{start_lat};{finish_lng},{finish_lat}"
    url = f"{OSRM_BASE_URL}/{coordinates_params}"

    response = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RouteResolutionError(
            f"OSRM could not find a route between '{start}' and '{finish}'"
        )

    route = data["routes"][0]
    distance_meters = route["distance"]

    raw_coords = route["geometry"]["coordinates"]
    geometry = [[lat, lng] for lng, lat in raw_coords]

    return {
        "distance_miles": round(distance_meters * METERS_TO_MILES, 2),
        "geometry": geometry,
    }
