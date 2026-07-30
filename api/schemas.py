from ninja import Schema


class RouteRequest(Schema):
    start: str
    finish: str


class FuelStop(Schema):
    name: str
    latitude: float
    longitude: float
    price_per_gallon: float
    cost: float
    distance_along_route_miles: float


class RouteResponse(Schema):
    total_distance_miles: float
    total_fuel_cost: float
    route_geometry: list[list[float]]
    fuel_stops: list[FuelStop]
