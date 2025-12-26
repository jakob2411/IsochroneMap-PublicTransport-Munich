import json
import folium
import geopandas as gpd

TARGETS = {
    "Hauptbahnhof": {
        "coords": (48.1403145, 11.56112),
        "train_file": "directions_results_hbf.json",
        "bike_file": "directions_results_hbf_bike.json",
    },
    "Flughafen": {
        "coords": (48.35389065534375, 11.786086141168415),
        "train_file": "directions_results_airport.json",
        "bike_file": None,
    },
}

MAP_FILE = "munich_hbf_airport.html"


def interpolate_color(val, color1, color2):
    c1 = [int(color1[i:i+2], 16) for i in (1, 3, 5)]
    c2 = [int(color2[i:i+2], 16) for i in (1, 3, 5)]
    c = [int(c1[j] + (c2[j] - c1[j]) * val) for j in range(3)]
    return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"


def get_color(duration):
    if duration < 5:
        return "#2196f3"
    if duration < 10:
        return "#1ec400"
    if duration < 20:
        return interpolate_color((duration - 10) / 10, "#1ec400", "#ffe600")
    if duration < 40:
        return interpolate_color((duration - 20) / 20, "#ffe600", "#ff9900")
    if duration < 60:
        return interpolate_color((duration - 40) / 20, "#ff9900", "#ff3300")
    if duration < 100:
        return interpolate_color((duration - 60) / 40, "#ff3300", "#b30000")
    return "#000000"


map_munich = folium.Map(location=TARGETS["Hauptbahnhof"]["coords"], zoom_start=5, tiles="CartoDB positron")

for name, info in TARGETS.items():
    for mode in ["train", "bike"]:
        if mode == "bike" and info.get("bike_file") is None:
            continue

        layer_name = f"{name} ({mode})"
        layer_group = folium.FeatureGroup(name=layer_name, show=(name == "Hauptbahnhof" and mode == "train"))
        file_key = f"{mode}_file"
        try:
            with open(info[file_key], "r", encoding="utf-8") as f:
                api_results = json.load(f)
        except FileNotFoundError:
            print(f"Missing file: {info[file_key]}")
            continue

        for entry in api_results:
            origin = entry["origin"]
            response = entry["response"]
            routes = response.get("routes", [])
            if not routes:
                continue

            duration = routes[0]["legs"][0]["duration"]["value"] / 60
            steps = routes[0]["legs"][0].get("steps", [])
            popup_html = "<div style='font-size:13px;'><b>Total time:</b> %.1f min<br><b>Route:</b><br>" % duration
            for step in steps:
                instruction = step.get("html_instructions", "")
                line = ""
                if "transit_details" in step:
                    transit = step["transit_details"]
                    line_name = transit["line"].get("short_name", transit["line"].get("name", ""))
                    line = f" ({line_name} -> {transit['headsign']})"
                popup_html += f"• {instruction}{line}<br>"
            popup_html += "</div>"

            folium.CircleMarker(
                location=(origin[0], origin[1]),
                radius=7,
                color=get_color(duration),
                fill=True,
                fill_color=get_color(duration),
                fill_opacity=0.85,
                tooltip=f"{duration:.1f} min",
                popup=folium.Popup(popup_html, max_width=400),
            ).add_to(layer_group)

        target_icon = folium.Icon(color="red" if mode == "train" else "darkgreen", icon="train" if mode == "train" else "bicycle", prefix="fa")
        folium.Marker(info["coords"], popup=f"<b>{name}</b><br>(destination)", icon=target_icon).add_to(layer_group)
        layer_group.add_to(map_munich)

try:
    gdf = gpd.read_file("gis_osm_railways_free_1.shp")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    folium.GeoJson(
        gdf,
        name="Rail network",
        style_function=lambda x: {"color": "#555", "weight": 1.5, "opacity": 0.7},
    ).add_to(map_munich)
except Exception as exc:
    print(f"Rail overlay skipped: {exc}")

legend_html = """
<div style="
    position: fixed;
    bottom: 30px; left: 30px; width: 160px;
    background: rgba(255,255,255,0.7);
    z-index:9999; font-size:13px;
    padding: 10px 14px 8px 14px; border-radius:12px;
    box-shadow: 1px 1px 6px #bbb;
">
<b style="font-size:14px;">Travel time (min)</b><br>
<div style="margin-top:8px;">
    <span style="display:inline-block; width:14px; height:14px; background:#2196f3; border-radius:50%; margin-right:8px; border:1px solid #2196f3;"></span> < 5<br>
    <span style="display:inline-block; width:14px; height:14px; background:#1ec400; border-radius:50%; margin-right:8px; border:1px solid #1ec400;"></span> 5-10<br>
    <span style="display:inline-block; width:14px; height:14px; background:#ffe600; border-radius:50%; margin-right:8px; border:1px solid #ffe600;"></span> 10-20<br>
    <span style="display:inline-block; width:14px; height:14px; background:#ff9900; border-radius:50%; margin-right:8px; border:1px solid #ff9900;"></span> 20-40<br>
    <span style="display:inline-block; width:14px; height:14px; background:#ff3300; border-radius:50%; margin-right:8px; border:1px solid #ff3300;"></span> 40-60<br>
    <span style="display:inline-block; width:14px; height:14px; background:#b30000; border-radius:50%; margin-right:8px; border:1px solid #b30000;"></span> 60-100<br>
    <span style="display:inline-block; width:14px; height:14px; background:#000000; border-radius:50%; margin-right:8px; border:1px solid #000000;"></span> > 100
</div>
</div>
"""
map_munich.get_root().html.add_child(folium.Element(legend_html))

license_html = """
<div style="
    position: fixed;
    bottom: 30px; right: 30px; width: 260px;
    background: rgba(255,255,255,0.7);
    z-index:9999; font-size:12px;
    padding: 8px 10px; border-radius:10px;
    box-shadow: 1px 1px 6px #bbb;
">
Directions data © Google; usage subject to Google Maps Platform Terms. Station coordinates from MVV open data. Rail overlay from OSM/geofabrik shapefile.
</div>
"""
map_munich.get_root().html.add_child(folium.Element(license_html))

folium.LayerControl(collapsed=False).add_to(map_munich)
map_munich.save(MAP_FILE)
print(f"Map saved: {MAP_FILE}")
