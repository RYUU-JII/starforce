import json
import os

file_path = r"c:\Users\113ji\Desktop\Projects\스타포스시뮬레이터\crawler\sessions\patch_20260130_0855\hourly_snapshots.jsonl"

if not os.path.exists(file_path):
    print("File not found.")
    exit()

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    try:
        json.loads(line)
    except json.JSONDecodeError as e:
        print(f"Line {i+1} is corrupted: {e}")
        # print first 100 chars
        print(f"Content: {line[:100]}...")
