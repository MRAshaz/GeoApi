"""
Management command: load_fuel_prices

Loads the given fuel-prices-for-be-assessment.csv file as-is (no edits to
source data), and enriches each row with approximate lat/lng by joining
City+State against a local GeoNames US places dump.

Usage:
    python manage.py load_fuel_prices \
        --csv data/fuel-prices-for-be-assessment.csv \
        --geonames data/geonames_us.txt

Download geonames_us.txt from:
    http://download.geonames.org/export/dump/US.zip  (unzip -> US.txt)
"""

import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import FuelStation

# GeoNames US.txt column indices (tab-separated, no header row)
# geonameid, name, asciiname, alternatenames, latitude, longitude,
# feature_class, feature_code, country_code, cc2, admin1_code, ...
GEO_NAME = 1
GEO_LAT = 4
GEO_LON = 5
GEO_FEATURE_CLASS = 6
GEO_COUNTRY = 8
GEO_ADMIN1 = 10
GEO_POPULATION = 14


class Command(BaseCommand):
    help = "Load fuel price CSV and enrich with lat/lng from a local GeoNames US dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="data/fuel-prices-for-be-assessment.csv",
            help="Path to the given fuel price CSV (unmodified).",
        )
        parser.add_argument(
            "--geonames",
            default="data/geonames_us.txt",
            help="Path to the downloaded GeoNames US.txt file.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing FuelStation rows before loading.",
        )

    def handle(self, *args, **options):
        geo_lookup = self._build_geo_lookup(options["geonames"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Built GeoNames lookup: {len(geo_lookup)} city/state keys"
            )
        )

        if options["clear"]:
            deleted, _ = FuelStation.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing rows"))

        stations, unmatched = self._build_stations(options["csv"], geo_lookup)

        with transaction.atomic():
            FuelStation.objects.bulk_create(stations, batch_size=1000)

        total = len(stations)
        matched = sum(1 for s in stations if s.latitude is not None)
        self.stdout.write(self.style.SUCCESS(f"Loaded {total} stations"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Geocoded (matched): {matched} ({matched / total * 100:.1f}%)"
            )
        )
        if unmatched:
            self.stdout.write(
                self.style.WARNING(
                    f"Unmatched city/state pairs: {len(unmatched)} "
                    f"(examples: {list(unmatched)[:10]})"
                )
            )

    def _build_geo_lookup(self, geonames_path):
        """
        Build {(CITY_UPPER, STATE): (lat, lon)} from the GeoNames US dump.
        Keeps the highest-population match when multiple places share a
        name within the same state (e.g. two small towns both named
        "Fairview" in the same state).
        """
        lookup = {}
        best_population = {}

        with open(geonames_path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) <= GEO_POPULATION:
                    continue
                if row[GEO_COUNTRY] != "US":
                    continue
                if row[GEO_FEATURE_CLASS] != "P":  # populated place only
                    continue

                name = row[GEO_NAME].strip().upper()
                state = row[GEO_ADMIN1].strip().upper()
                key = (name, state)

                try:
                    population = int(row[GEO_POPULATION] or 0)
                except ValueError:
                    population = 0

                if key not in best_population or population > best_population[key]:
                    try:
                        lat = float(row[GEO_LAT])
                        lon = float(row[GEO_LON])
                    except ValueError:
                        continue
                    lookup[key] = (lat, lon)
                    best_population[key] = population

        return lookup

    def _build_stations(self, csv_path, geo_lookup):
        stations = []
        unmatched = set()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = row["City"].strip()
                state = row["State"].strip().upper()
                key = (city.upper(), state)
                coords = geo_lookup.get(key)

                if coords is None:
                    unmatched.add(f"{city}, {state}")

                price = self._parse_price(row["Retail Price"])
                if price is None:
                    continue  # skip unparseable rows rather than crash the whole load

                stations.append(
                    FuelStation(
                        opis_id=self._parse_int(row["OPIS Truckstop ID"]),
                        name=row["Truckstop Name"].strip(),
                        address=row["Address"].strip(),
                        city=city,
                        state=state,
                        rack_id=self._parse_int(row["Rack ID"]),
                        retail_price=price,
                        latitude=coords[0] if coords else None,
                        longitude=coords[1] if coords else None,
                    )
                )

        return stations, unmatched

    @staticmethod
    def _parse_price(raw):
        try:
            return Decimal(raw.strip())
        except (InvalidOperation, AttributeError):
            return None

    @staticmethod
    def _parse_int(raw):
        try:
            return int(raw.strip())
        except (ValueError, AttributeError):
            return None
