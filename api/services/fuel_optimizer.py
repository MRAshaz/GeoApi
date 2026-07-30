from api.models import FuelStation
from .geo_utils import build_route_distance_index, nearest_point_on_route

CORRIDOR_WIDTHS_MILES = [10, 20, 30, 50]

MAX_STOPS_SAFETY_CAP = 50

MILES_PER_DEGREE = 69.0


def _get_candidate_stations(geometry, max_corridor_miles):
    lats = [point[0] for point in geometry]
    lngs = [point[1] for point in geometry]

    padding_degrees = max_corridor_miles / MILES_PER_DEGREE

    return FuelStation.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False,
        latitude__gte=min(lats) - padding_degrees,
        latitude__lte=max(lats) + padding_degrees,
        longitude__gte=min(lngs) - padding_degrees,
        longitude__lte=max(lngs) + padding_degrees,
    )


def _precompute_station_positions(candidates, geometry, distances):
    positions = []
    for station in candidates:
        distance_along, distance_off = nearest_point_on_route(
            station.latitude, station.longitude, geometry, distances
        )
        positions.append((station, distance_along, distance_off))
    return positions


def _find_best_station_in_window(
    station_positions, window_start_miles, window_end_miles
):
    for corridor_width in CORRIDOR_WIDTHS_MILES:
        best_station = None
        best_price = None
        best_distance_along = None
        best_distance_off = None

        for station, distance_along, distance_off in station_positions:
            in_window = window_start_miles <= distance_along <= window_end_miles
            in_corridor = distance_off <= corridor_width

            if not (in_window and in_corridor):
                continue

            if best_price is None or station.retail_price < best_price:
                best_station = station
                best_price = station.retail_price
                best_distance_along = distance_along
                best_distance_off = distance_off

        if best_station is not None:
            return best_station, best_distance_along, best_distance_off

    return None, None, None


def plan_fuel_stops(geometry, total_distance_miles, max_range_miles=500, mpg=10):
    distances = build_route_distance_index(geometry)
    gallons_per_fill = max_range_miles / mpg

    candidates = list(
        _get_candidate_stations(geometry, max_corridor_miles=CORRIDOR_WIDTHS_MILES[-1])
    )

    station_positions = _precompute_station_positions(candidates, geometry, distances)

    stops = []
    total_cost = 0.0
    current_position_miles = 0.0
    iterations = 0
    used_station_ids = set()

    while total_distance_miles - current_position_miles > max_range_miles:
        iterations += 1
        if iterations > MAX_STOPS_SAFETY_CAP:
            break

        window_start = current_position_miles
        window_end = current_position_miles + max_range_miles

        remaining_positions = [
            p for p in station_positions if p[0].id not in used_station_ids
        ]

        station, distance_along, distance_off = _find_best_station_in_window(
            remaining_positions, window_start, window_end
        )

        if station is None:
            # No station found even at the widest corridor width for
            # this stretch of route - stop planning further stops
            # rather than guessing or crashing.
            break

        used_station_ids.add(station.id)
        price = float(station.retail_price)
        cost = round(gallons_per_fill * price, 2)
        total_cost += cost

        stops.append(
            {
                "name": station.name,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "price_per_gallon": price,
                "gallons_purchased": gallons_per_fill,
                "cost": cost,
                "distance_along_route_miles": round(distance_along, 2),
            }
        )

        current_position_miles = distance_along

    return stops, round(total_cost, 2)
