import httpx
import os
from dotenv import load_dotenv

load_dotenv()
OPENAQ_KEY = os.getenv("OPENAQ_API_KEY", "")
headers = {"X-API-Key": OPENAQ_KEY}

# Fetch parameters
url = "https://api.openaq.org/v3/parameters"
with httpx.Client(timeout=15) as client:
    resp = client.get(url, headers=headers)
    print("OpenAQ parameters:")
    for param in resp.json().get("results", []):
         print(f"ID: {param.get('id')}, Name: {param.get('name')}, Display: {param.get('displayName')}")
