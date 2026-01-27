import os
import json

TARGET_DIR = "audit_data"
DEFAULT_EVENT = "스타포스 이벤트 미적용"

def fix_events():
    count = 0
    if not os.path.exists(TARGET_DIR):
        print(f"Directory {TARGET_DIR} not found.")
        return

    for filename in os.listdir(TARGET_DIR):
        if not filename.endswith(".json"):
            continue
            
        filepath = os.path.join(TARGET_DIR, filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            meta = data.get("meta", {})
            current_event = meta.get("event", "").strip()
            
            # If event is missing, empty, or 'No Event', update it
            if not current_event or current_event == "No Event":
                meta["event"] = DEFAULT_EVENT
                data["meta"] = meta
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"Updated {filename}")
                count += 1
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"✅ Finished! Updated {count} files.")

if __name__ == "__main__":
    fix_events()
