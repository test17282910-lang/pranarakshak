import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"

url = f"https://api.waqi.info/search/?keyword=hyderabad&token={token}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
   data = json.loads(response.read().decode())
   print("Search results for 'hyderabad':")
   for station in data.get("data", []):
       print(f"Name: {station.get('station', {}).get('name')}")
       print(f"Geo: {station.get('station', {}).get('geo')}")
       print(f"UID: {station.get('uid')}")
       print("-" * 20)
