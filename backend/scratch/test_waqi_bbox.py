import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"
lat, lon = 17.385044, 78.486671

# Define bounding box +/- 0.5 degrees around Hyderabad
lat1, lng1 = lat - 0.5, lon - 0.5
lat2, lng2 = lat + 0.5, lon + 0.5

url = f"https://api.waqi.info/map/bounds/?latlng={lat1},{lng1},{lat2},{lng2}&token={token}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        stations = data.get("data", [])
        print(f"Found {len(stations)} stations in bounding box:")
        for s in stations:
            station_name = s.get("station", {}).get("name", "").encode('ascii', 'ignore').decode('ascii')
            print(f"Name: {station_name}")
            print(f"UID: {s.get('uid')}")
            print(f"AQI: {s.get('aqi')}")
            print(f"Coords: {s.get('lat')}, {s.get('lon')}")
            # Get details
            detail_url = f"https://api.waqi.info/feed/@{s.get('uid')}/?token={token}"
            detail_req = urllib.request.Request(detail_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(detail_req) as detail_res:
                detail_data = json.loads(detail_res.read().decode())
                print(f"Updated: {detail_data.get('data', {}).get('time', {}).get('s')}")
            print("-" * 20)
except Exception as e:
    print(f"Failed: {e}")
