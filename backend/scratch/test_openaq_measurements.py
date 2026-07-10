import httpx
import os
from dotenv import load_dotenv

load_dotenv()
OPENAQ_KEY = os.getenv("OPENAQ_API_KEY", "")
headers = {"X-API-Key": OPENAQ_KEY}

# Let's test the correct v3 path for location measurements
loc_id = "407"
url = f"https://api.openaq.org/v3/locations/{loc_id}/measurements"
params = {
    "limit": 10
}

with httpx.Client(timeout=15) as client:
    resp = client.get(url, params=params, headers=headers)
    print("OpenAQ Locations Measurements response status:", resp.status_code)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        print("Measurements found:", len(results))
        if results:
            print("Sample:", results[0])
    else:
        print("Response:", resp.text)
