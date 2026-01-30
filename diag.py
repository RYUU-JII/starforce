import requests
try:
    r = requests.get('http://localhost:8000/api/audit/temporal-gap', timeout=5)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(f"Stars in data: {list(data.keys())}")
    if "17" in data:
        print(f"17* points: {len(data['17']['real']['hourly'])}")
        print(f"17* sample: {data['17']['real']['hourly'][0] if data['17']['real']['hourly'] else 'empty'}")
    else:
        print("17* data missing!")
except Exception as e:
    print(f"Error: {e}")
