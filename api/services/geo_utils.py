import math

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * (
        math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_MILES * c


def build_route_distance_index(geometry: list[list[float]]) -> list[float]:
    distances = [0.0]
    for i in range(1, len(geometry)):
        lat1, lng1 = geometry[i - 1]
        lat2, lng2 = geometry[i]
        segment_miles = haversine_miles(lat1, lng1, lat2, lng2)
        distances.append(distances[-1] + segment_miles)
    return distances


def nearest_point_on_route(lat: float, lng: float, geometry: list, distances: list):
    best_index = 0
    best_distance = float("inf")

    for i, (route_lat, route_lng) in enumerate(geometry):
        d = haversine_miles(lat, lng, route_lat, route_lng)
        if d < best_distance:
            best_distance = d
            best_index = i

    return distances[best_index], best_distance
