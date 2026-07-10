import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"

cities = {
    "Hyderabad": "geo:17.385044;78.486671",
    "Mumbai": "geo:19.0760;72.8777",
    "Bangalore": "geo:12.9716;77.5946",
    "Delhi Center": "geo:28.6139;77.2090",
    "San Francisco": "geo:37.7749;-122.4194"
}

for name, endpoint in cities.items():
    url = f"https://api.waqi.info/feed/{endpoint}/?token={token}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            city_name = data.get("data", {}).get("city", {}).get("name")
            geo = data.get("data", {}).get("city", {}).get("geo")
            print(f"{name}: {city_name} (coords: {geo})")
    except Exception as e:
        print(f"{name} failed: {e}")
