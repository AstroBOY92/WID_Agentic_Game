'''
import os, requests, math

def find_city_center(query: str):
    # Use Nominatim (OSM) for geocoding (courteous usage: light traffic)
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": query, "format":"json", "limit": 1}, timeout=20,
                         headers={"User-Agent":"TripSmith/0.1 (educational)"})
        r.raise_for_status()
        arr = r.json()
        if not arr: return None
        hit = arr[0]
        return {"city": hit.get("display_name","").split(",")[0],
                "country": "", "lat": float(hit["lat"]), "lon": float(hit["lon"])}
    except Exception:
        return None

def get_pois_nearby(lat, lon, radius=3000, kinds="interesting_places,foods", limit=40):
    key = os.getenv("OPENTRIPMAP_API_KEY")
    if not key:
        # fallback: return empty list; the agent can still plan
        return []
    r = requests.get("https://api.opentripmap.com/0.1/en/places/radius",
                     params={"apikey": key, "radius": radius, "lon": lon, "lat": lat,
                             "kinds": kinds, "limit": limit},
                     timeout=30)
    r.raise_for_status()
    feats = r.json().get("features", [])
    pois = []
    for f in feats:
        props = f.get("properties", {})
        geom = f.get("geometry",{})
        coords = geom.get("coordinates",[None,None])
        pois.append({"name": props.get("name","POI"),
                     "lat": coords[1], "lon": coords[0],
                     "rate": props.get("rate")})
    return pois'''
import os, requests, math

def find_city_center(query: str):
    # Use Nominatim (OSM) for geocoding (courteous usage: light traffic)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            timeout=20,
            headers={"User-Agent": "BigEarsAI/1.0 (educational)"}
        )
        r.raise_for_status()
        arr = r.json()
        if not arr:
            return None
        hit = arr[0]
        return {
            "city": hit.get("display_name", "").split(",")[0],
            "country": "",
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
        }
    except Exception:
        return None


def get_pois_nearby(lat, lon, radius=3000, kinds="interesting_places,foods", limit=40):
    """
    Get nearby POIs from OpenStreetMap (via Overpass API).
    This is a fallback when no OPENTRIPMAP_API_KEY is available.
    """
    try:
        # Overpass API query to fetch restaurants, cafes, bars, museums, parks, and attractions
        query = f"""
        [out:json][timeout:25];
        (
          node["tourism"](around:{radius},{lat},{lon});
          node["amenity"="restaurant"](around:{radius},{lat},{lon});
          node["amenity"="cafe"](around:{radius},{lat},{lon});
          node["amenity"="bar"](around:{radius},{lat},{lon});
          node["amenity"="museum"](around:{radius},{lat},{lon});
          node["leisure"="park"](around:{radius},{lat},{lon});
        );
        out center {limit};
        """

        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
            headers={"User-Agent": "BigEarsAI/1.0"},
        )
        r.raise_for_status()
        data = r.json()

        pois = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name")
            if not name:
                continue
            pois.append({
                "name": name,
                "lat": el.get("lat"),
                "lon": el.get("lon"),
                "type": el.get("tags", {}).get("amenity")
                        or el.get("tags", {}).get("tourism")
                        or el.get("tags", {}).get("leisure", "poi")
            })
        return pois
    except Exception as e:
        print(f"[WARN] Overpass API error: {e}")
        return []
