from ninja import Router
from .schemas import RouteRequest, RouteResponse
from .services.osrm_client import get_route
from .services.fuel_optimizer import plan_fuel_stops

router = Router(tags=["route"])


@router.post("/route", response=RouteResponse)
def plan_route(request, payload: RouteRequest):
    route = get_route(payload.start, payload.finish)

    stops, total_cost = plan_fuel_stops(
        geometry=route["geometry"],
        total_distance_miles=route["distance_miles"],
        max_range_miles=500,
        mpg=10,
    )

    return {
        "total_distance_miles": route["distance_miles"],
        "total_fuel_cost": total_cost,
        "route_geometry": route["geometry"],
        "fuel_stops": stops,
    }
