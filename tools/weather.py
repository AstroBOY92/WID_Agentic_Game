import requests, datetime as dt

def get_weather_daily(lat, lon, start_iso, end_iso, timezone="auto"):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": timezone, "start_date": start_iso, "end_date": end_iso
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def get_weather_daily_by_city(city, lat, lon, start_iso, end_iso):
    if not (start_iso and end_iso):
        # default to a 3-day window from today if not provided
        today = dt.date.today()
        start_iso = today.isoformat()
        end_iso = (today + dt.timedelta(days=3)).isoformat()
    return get_weather_daily(lat, lon, start_iso, end_iso)
