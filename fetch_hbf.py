import os
import pandas as pd
import requests
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GOOGLE_MAPS_API_KEY in .env before running.")

TARGET = (48.140386, 11.560027)  # Munich Hauptbahnhof
OUTPUT_FILE = "directions_results_hbf.json"
EXCEL_FILE = "cords.xlsx"  # Excel file with coordinates

# Time window: 08:00 - 09:00 on 25 Aug 2025
departure_start = datetime.datetime(2025, 8, 25, 8, 0)
departure_end = datetime.datetime(2025, 8, 25, 9, 0)
departure_interval = 5  # minutes

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


def fetch_route_time(lat, lon, departure_ts):
    url = (
        "https://maps.googleapis.com/maps/api/directions/json?"
        f"origin={lat},{lon}&destination={TARGET[0]},{TARGET[1]}"
        "&mode=transit"
        "&transit_mode=bus|subway|train|tram|rail"
        f"&departure_time={departure_ts}"
        f"&key={API_KEY}"
    )
    response = requests.get(url).json()

    if response.get("status") == "OK" and response.get("routes"):
        valid_routes = [
            r for r in response["routes"]
            if r.get("legs") and r["legs"][0].get("duration")
        ]
        if valid_routes:
            shortest_route = min(valid_routes, key=lambda r: r["legs"][0]["duration"]["value"])
            return shortest_route
    return None


def fetch_route(lat, lon):
    current_time = departure_start
    best_route = None
    best_duration = float("inf")

    while current_time <= departure_end:
        departure_ts = int(current_time.timestamp())
        route = fetch_route_time(lat, lon, departure_ts)
        if route:
            duration = route["legs"][0]["duration"]["value"]
            if duration < best_duration:
                best_duration = duration
                best_route = route
        current_time += datetime.timedelta(minutes=departure_interval)

    response = {"routes": [best_route]} if best_route else {"routes": []}
    return {"origin": [lat, lon], "destination": TARGET, "response": response}


api_results = []
MAX_WORKERS = 50
REQUESTS_PER_SECOND = 50

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(fetch_route, lat, lon): (lat, lon) for lat, lon in origins}
    start_time = time.time()
    completed_requests = 0

    for i, future in enumerate(as_completed(futures), 1):
        result = future.result()
        api_results.append(result)
        completed_requests += 1

        elapsed = time.time() - start_time
        if elapsed > 0 and completed_requests / elapsed > REQUESTS_PER_SECOND:
            time.sleep(0.01)

        print(f"[{i}/{len(origins)}] Done: {result['origin']}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(api_results, f, ensure_ascii=False, indent=2)

print(f"Saved API results to {OUTPUT_FILE}")
