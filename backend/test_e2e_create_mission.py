import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(r'c:\Users\kunwa\Desktop\JeevanMarg-Agent\backend')

from fastapi.testclient import TestClient
from app.main import app

def run_test():
    client = TestClient(app)
    
    # 1. Login to get token as dispatcher
    print("Logging in...")
    login_res = client.post("/api/v1/auth/login", json={
        "username": "dispatcher",
        "password": "dispatch123"
    })
    if login_res.status_code != 200:
        print("Login failed:", login_res.text)
        return
    
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful! Token acquired.")
    
    # 2. Create mission
    mission_payload = {
        "origin_name": "Salt Lake Sector V",
        "origin_lat": 22.57264,
        "origin_lng": 88.42564,
        "destination_name": "Ruby General Hospital",
        "destination_lat": 22.51264,
        "destination_lng": 88.40164
    }
    print("\nCreating mission...")
    create_res = client.post("/api/v1/missions", json=mission_payload, headers=headers)
    if create_res.status_code != 201:
        print("Mission creation failed:", create_res.text)
        return
    
    mission = create_res.json()
    mission_id = mission["id"]
    print(f"Mission created successfully! ID: {mission_id}, Code: {mission['mission_code']}, Status: {mission['status']}")
    
    # 3. Get routes
    print("\nFetching routes for mission...")
    routes_res = client.get(f"/api/v1/missions/{mission_id}/routes", headers=headers)
    if routes_res.status_code != 200:
        print("Fetching routes failed:", routes_res.text)
        return
    
    routes = routes_res.json()
    print(f"Number of routes returned: {len(routes)}")
    for i, r in enumerate(routes):
        print(f"Route #{i+1}: Type={r['route_type']}, Name={r['route_name']}, Waypoints={len(r['waypoints'])}, Source={r['route_source']}")

if __name__ == "__main__":
    run_test()
