import os
from dotenv import load_dotenv
from db import db

load_dotenv()

# Get all users
users = db.client.table("users").select("*").execute()
print("Users in DB:")
for u in users.data:
    print(f"ID: {u['id']}")
    print(f"Name: {u['name']}")
    print(f"Condition: {u['condition']}")
    print(f"Severity: {u['severity']}")
    print(f"Symptoms: {u['symptoms']}")
    print(f"Triggers: {u['personalized_issue']}")
    print("-" * 40)
