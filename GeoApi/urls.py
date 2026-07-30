from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from api.views import router as fuel_router

api = NinjaAPI(title="Fuel Route API", version="1.0.0")
api.add_router("/", fuel_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
