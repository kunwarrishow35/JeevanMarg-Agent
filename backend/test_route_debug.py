import sys
import os

# Add backend directory to path
sys.path.append(r'c:\Users\kunwa\Desktop\JeevanMarg-Agent\backend')

from data.route_sim import generate_route_data, generate_alternative_route_data

origin = {"lat": 22.57264, "lng": 88.42564, "name": "Salt Lake Sector V"}
destination = {"lat": 22.51264, "lng": 88.40164, "name": "Ruby General Hospital"}

print("--- Testing primary route generation ---")
try:
    res = generate_route_data(origin, destination)
    print("Success!")
    print("Route Name:", res.get("route_name"))
    print("Waypoints count:", len(res.get("waypoints", [])))
    print("Segments count:", len(res.get("segments", [])))
    print("Distance (km):", res.get("distance_km"))
    print("Base ETA (min):", res.get("base_eta_minutes"))
    print("Route Source:", res.get("route_source", "Not returned"))
except Exception as e:
    print("Failed with exception:", e)

print("\n--- Testing alternative/recovery route generation ---")
try:
    res_alt = generate_alternative_route_data(origin, destination, avoid_segments=["seg_01"])
    print("Success!")
    print("Alternative Route Name:", res_alt.get("route_name"))
    print("Waypoints count:", len(res_alt.get("waypoints", [])))
    print("Segments count:", len(res_alt.get("segments", [])))
    print("Distance (km):", res_alt.get("distance_km"))
    print("Base ETA (min):", res_alt.get("base_eta_minutes"))
    print("Route Source:", res_alt.get("route_source", "Not returned"))
except Exception as e:
    print("Failed with exception:", e)
