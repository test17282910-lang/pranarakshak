import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("OPENAQ_API_KEY", "")
print("Key length:", len(key))
print("Key representation:", repr(key))
print("Key characters:")
for char in key:
    print(f"Char: {char} (Unicode: {ord(char)})")
