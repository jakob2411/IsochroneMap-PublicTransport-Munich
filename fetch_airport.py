import os
import pandas as pd
import requests
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GOOGLE_MAPS_API_KEY in .env before running.")

TARGET = (48.35389065534375, 11.786086141168415)  # Munich Airport
OUTPUT_FILE = "directions_results_airport.json"
EXCEL_FILE = "cords.xlsx"  # Excel file with coordinates

departure_dt = datetime.datetime(2025, 8, 25, 8, 0)
departure_ts = int(departure_dt.timestamp())

df = pd.read_excel(EXCEL_FILE)
origins = []
for _, row in df.iterrows():
    try:
        lat = float(row.iloc[0])
        lon = float(row.iloc[1])
        origins.append((lat, lon))
    except (ValueError, TypeError):
        continue

print(f"Loaded {len(origins)} origins from Excel")


def fetch_route(lat, lon):
    url = (
        "https://maps.googleapis.com/maps/api/directions/json?"
        f"origin={lat},{lon}&destination={TARGET[0]},{TARGET[1]}"
        "&mode=transit"
        "&transit_mode=train|bus|subway|tram"
        f"&departure_time={departure_ts}"
        f"&key={API_KEY}"
    )

    response = requests.get(url).json()

    if response.get("status") == "OK" and response.get("routes"):
        shortest_route = min(
            response["routes"],
            key=lambda r: r["legs"][0]["duration"]["value"]
        )
        response["routes"] = [shortest_route]

    return {
        "origin": [lat, lon],
        "destination": TARGET,
        "response": response
    }


api_results = []
with ThreadPoolExecutor(max_workers=50) as executor:
    futures = {executor.submit(fetch_route, lat, lon): (lat, lon) for lat, lon in origins}
    for i, future in enumerate(as_completed(futures), 1):
        result = future.result()
        api_results.append(result)
        print(f"[{i}/{len(origins)}] Done: {result['origin']}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(api_results, f, ensure_ascii=False, indent=2)

print(f"Saved API results to {OUTPUT_FILE}")
