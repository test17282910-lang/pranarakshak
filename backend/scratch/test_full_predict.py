import asyncio
import os
from dotenv import load_dotenv
from db import db
from data_fetcher import get_readings_for_location
import app

load_dotenv()

async def test_predict():
    user_id = "143942ef-cdfa-4603-8225-df69ef7e292c"
    user = db.get_user_by_id(user_id)
    print("User details:")
    print(user)
    
    lat = user.get("last_known_lat", 17.385044)
    lon = user.get("last_known_lon", 78.486671)
    print(f"\nUser location coords: {lat}, {lon}")
    
    # 1. Fetch readings
    print("\nRunning get_readings_for_location...")
    df, fetch_source = get_readings_for_location(lat, lon)
    print(f"Fetch Source: {fetch_source}")
    if df is not None:
        print(f"Dataframe length: {len(df)}")
        print("Last row of dataframe:")
        print(df.iloc[-1].to_dict())
    else:
        print("Dataframe is None!")

    # 2. Simulate complete predict payload
    class FakePayload:
        def __init__(self):
            self.user_id = user_id
            self.lat = lat
            self.lon = lon
            self.radius_km = 25
            self.condition = user.get("condition")
            self.severity = user.get("severity")

    print("\nRunning predict endpoint logic...")
    # Load model artifacts first if not loaded
    app._load_artifacts()
    res = await app.predict(FakePayload())
    print("\nPrediction Response:")
    print(f"Predicted AQI Raw: {res.predicted_aqi_raw}")
    print(f"Predicted AQI Adjusted: {res.predicted_aqi_adjusted}")
    print(f"Source: {res.prediction_source}")
    print(f"Alert Tier: {res.alert_tier}")
    print(f"Message: {res.alert_message}")

asyncio.run(test_predict())
