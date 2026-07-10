import urllib.request
import json

lat, lon = 17.385044, 78.486671

url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token=demo"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        city_name = data.get("data", {}).get("city", {}).get("name", "")
        # Safe printing to avoid terminal encoding errors
        print("Demo token:")
        print(city_name.encode('ascii', 'ignore').decode('ascii'))
        print(data.get("data", {}).get("city", {}).get("geo"))
except Exception as e:
    print(f"Demo token failed: {e}")
