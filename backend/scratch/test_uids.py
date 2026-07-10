import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"

uids = {
    "Somajiguda (14125)": "@14125",
    "Zoo Park (8677)": "@8677",
    "Sanathnagar (8182)": "@8182",
    "New Malakpet (14135)": "@14135"
}

for name, endpoint in uids.items():
    url = f"https://api.waqi.info/feed/{endpoint}/?token={token}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            status = data.get("status")
            if status == "ok":
                station_data = data.get("data", {})
                city_name = station_data.get("city", {}).get("name")
                update_time = station_data.get("time", {}).get("s")
                aqi = station_data.get("aqi")
                print(f"{name}: {city_name} -> AQI={aqi}, Updated={update_time}")
            else:
                print(f"{name}: Failed with status {status}")
    except Exception as e:
        print(f"{name} failed: {e}")
