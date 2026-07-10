import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"

# Test both orders for Hyderabad
coords_orders = {
    "lat;lng (17.385;78.486)": "geo:17.385044;78.486671",
    "lng;lat (78.486;17.385)": "geo:78.486671;17.385044"
}

for desc, endpoint in coords_orders.items():
    url = f"https://api.waqi.info/feed/{endpoint}/?token={token}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            city_name = data.get("data", {}).get("city", {}).get("name")
            geo = data.get("data", {}).get("city", {}).get("geo")
            print(f"{desc}: {city_name} (coords: {geo})")
    except Exception as e:
        print(f"{desc} failed: {e}")
