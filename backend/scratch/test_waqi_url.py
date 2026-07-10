import httpx

token = "dbc8cc734f4c589231c54c0ae66ce96d2a5bbbcf"
lat, lon = 17.385044, 78.486671

# Test 1: Using string URL with httpx
url1 = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}"
resp1 = httpx.get(url1)
print("Test 1 (direct URL string):")
print(resp1.json().get("data", {}).get("city", {}).get("name"))

# Test 2: Using manual socket / raw request or different lib
import urllib.request
import json
url2 = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}"
req = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
   data = json.loads(response.read().decode())
   print("Test 2 (urllib):")
   print(data.get("data", {}).get("city", {}).get("name"))

# Test 3: Check if there's a trailing slash issue or prefix issue
# Let's test Delhi coords to see if geo:lat;lng actually works for Delhi
url3 = f"https://api.waqi.info/feed/geo:28.6139;77.2090/?token={token}"
with urllib.request.urlopen(url3) as response:
   data = json.loads(response.read().decode())
   print("Test 3 (urllib Delhi):")
   print(data.get("data", {}).get("city", {}).get("name"))
