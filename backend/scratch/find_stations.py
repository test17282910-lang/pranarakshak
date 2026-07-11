import httpx, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

WAQI_TOKEN = os.getenv("WAQI_TOKEN", "")
OPENAQ_KEY = os.getenv("X-API-Key", "")

# Nearest WAQI station UIDs from previous search
NEAREST_UIDS = [14156, 14155, 14149, 8182, 8677, 14125, 14135]

print("=== Fetching each WAQI station directly by UID ===")
for uid in NEAREST_UIDS:
    try:
        r = httpx.get(f'https://api.waqi.info/feed/@{uid}/', params={'token': WAQI_TOKEN}, timeout=10)
        d = r.json()
        if d.get('status') == 'ok':
            data = d['data']
            aqi = data.get('aqi')
            name = data.get('city', {}).get('name', 'unknown')
            geo = data.get('city', {}).get('geo', [])
            pm25 = data.get('iaqi', {}).get('pm25', {}).get('v', '?')
            pm10 = data.get('iaqi', {}).get('pm10', {}).get('v', '?')
            updated = data.get('time', {}).get('s', '?')
            km = '?'
            if len(geo) == 2:
                dlat = float(geo[0]) - 17.5449
                dlon = float(geo[1]) - 78.6898
                km = round(((dlat**2 + dlon**2)**0.5) * 111, 1)
            print(f"  uid={uid} | {name} | {km}km | AQI={aqi} | PM2.5={pm25} PM10={pm10} | updated={updated}")
        else:
            print(f"  uid={uid} | ERROR: {d.get('data', 'unknown')}")
    except Exception as e:
        print(f"  uid={uid} | EXCEPTION: {e}")

print()
print("=== OpenAQ v2 fallback (measurements endpoint) ===")
try:
    r = httpx.get(
        'https://api.openaq.org/v2/measurements',
        params={'coordinates': '17.5449,78.6898', 'radius': 60000, 'parameter': 'pm25', 'limit': 5, 'sort': 'desc', 'order_by': 'datetime'},
        timeout=15
    )
    results = r.json().get('results', [])
    if results:
        for res in results[:5]:
            print(f"  location={res.get('location')} | value={res.get('value')} | date={res.get('date',{}).get('utc','?')}")
    else:
        print("  No results found")
except Exception as e:
    print(f"  ERROR: {e}")
