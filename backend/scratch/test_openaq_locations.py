import httpx
import os
from dotenv import load_dotenv

load_dotenv()
# Strip any trailing whitespace/carriage returns
OPENAQ_KEY = os.getenv("X-API-Key", "").strip()
headers = {"X-API-Key": OPENAQ_KEY}

# Fetch locations near Hyderabad coordinates
url = "https://api.openaq.org/v3/locations"
params = {
    "coordinates": "17.385044,78.486671",
    "radius": 25000,
    "parameters_id": "2,1",
    "limit": 5
}

with httpx.Client(timeout=15) as client:
    resp = client.get(url, params=params, headers=headers)
    print("OpenAQ Locations response status (stripped key):", resp.status_code)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        print(f"Found {len(results)} locations:")
        for r in results:
            print(f"ID: {r.get('id')}, Name: {r.get('name')}, Coords: {r.get('coordinates')}")
    else:
        print("Response:", resp.text)
