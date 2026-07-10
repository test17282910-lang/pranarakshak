import urllib.request
import json

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"

# Test exactly Somajiguda coords
url1 = f"https://api.waqi.info/feed/geo:17.417094;78.457437/?token={token}"
req = urllib.request.Request(url1, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
   data = json.loads(response.read().decode())
   print("Test Somajiguda coords:")
   print(data.get("data", {}).get("city", {}).get("name"))
