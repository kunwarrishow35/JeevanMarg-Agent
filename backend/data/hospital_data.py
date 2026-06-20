"""Hospital seed data for Delhi NCR region."""

HOSPITALS = [
    {
        "id": "hosp_001",
        "name": "AIIMS Delhi",
        "type": "trauma_center",
        "trauma_level": 1,
        "lat": 28.5672,
        "lng": 77.2100,
        "address": "Sri Aurobindo Marg, Ansari Nagar, New Delhi",
        "emergency_beds": 120,
        "specialties": ["trauma", "neurosurgery", "cardiology", "burns"],
    },
    {
        "id": "hosp_002",
        "name": "Safdarjung Hospital",
        "type": "trauma_center",
        "trauma_level": 1,
        "lat": 28.5685,
        "lng": 77.2065,
        "address": "Ansari Nagar West, New Delhi",
        "emergency_beds": 80,
        "specialties": ["trauma", "orthopedics", "general_surgery"],
    },
    {
        "id": "hosp_003",
        "name": "Ram Manohar Lohia Hospital",
        "type": "trauma_center",
        "trauma_level": 2,
        "lat": 28.6270,
        "lng": 77.2050,
        "address": "Baba Kharak Singh Marg, New Delhi",
        "emergency_beds": 60,
        "specialties": ["trauma", "general_surgery", "orthopedics"],
    },
    {
        "id": "hosp_004",
        "name": "Sir Ganga Ram Hospital",
        "type": "hospital",
        "trauma_level": 2,
        "lat": 28.6380,
        "lng": 77.1900,
        "address": "Rajinder Nagar, New Delhi",
        "emergency_beds": 45,
        "specialties": ["cardiology", "neurosurgery", "oncology"],
    },
    {
        "id": "hosp_005",
        "name": "Max Super Speciality Hospital",
        "type": "hospital",
        "trauma_level": 2,
        "lat": 28.5670,
        "lng": 77.2730,
        "address": "Saket, New Delhi",
        "emergency_beds": 50,
        "specialties": ["trauma", "cardiology", "neurology"],
    },
    {
        "id": "hosp_006",
        "name": "Lok Nayak Hospital",
        "type": "trauma_center",
        "trauma_level": 1,
        "lat": 28.6370,
        "lng": 77.2390,
        "address": "Jawaharlal Nehru Marg, New Delhi",
        "emergency_beds": 100,
        "specialties": ["trauma", "burns", "general_surgery"],
    },
    {
        "id": "hosp_007",
        "name": "Apollo Hospital",
        "type": "hospital",
        "trauma_level": 2,
        "lat": 28.5560,
        "lng": 77.2840,
        "address": "Sarita Vihar, Mathura Road, New Delhi",
        "emergency_beds": 40,
        "specialties": ["cardiology", "orthopedics", "neurology"],
    },
    {
        "id": "hosp_008",
        "name": "GTB Hospital",
        "type": "trauma_center",
        "trauma_level": 1,
        "lat": 28.6850,
        "lng": 77.3110,
        "address": "Dilshad Garden, Delhi",
        "emergency_beds": 70,
        "specialties": ["trauma", "general_surgery", "burns"],
    },
]


def get_nearby_hospitals_data(lat: float, lng: float, radius_km: float = 10.0) -> list[dict]:
    """Get hospitals near a given location within radius."""
    import math
    results = []
    for h in HOSPITALS:
        dist = _haversine(lat, lng, h["lat"], h["lng"])
        if dist <= radius_km:
            results.append({**h, "distance_km": round(dist, 2)})
    results.sort(key=lambda x: x["distance_km"])
    return results


def get_trauma_centers_data(lat: float, lng: float) -> list[dict]:
    """Get trauma centers (Level 1 & 2) near a location."""
    import math
    results = []
    for h in HOSPITALS:
        if h["type"] == "trauma_center":
            dist = _haversine(lat, lng, h["lat"], h["lng"])
            results.append({**h, "distance_km": round(dist, 2)})
    results.sort(key=lambda x: x["distance_km"])
    return results


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using haversine formula (km)."""
    import math
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
