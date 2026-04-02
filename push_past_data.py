import requests
import os
import json

# API endpoint
API_URL = "http://172.16.7.119:8004/imd_data.php"

# Download folder path
download_folder = "Download"

# Get all date folders
date_folders = sorted([d for d in os.listdir(download_folder) if os.path.isdir(os.path.join(download_folder, d))])

print(f"Found {len(date_folders)} date folders")
print(f"Pushing cluster_temperature.json files to {API_URL}\n")

success_count = 0
error_count = 0

for date_folder in date_folders:
    folder_path = os.path.join(download_folder, date_folder)
    json_file = os.path.join(folder_path, "cluster_temperature.json")
    
    # Check if cluster_temperature.json exists
    if not os.path.exists(json_file):
        print(f"❌ {date_folder}: cluster_temperature.json not found")
        error_count += 1
        continue
    
    # Read the JSON file
    try:
        with open(json_file, "r") as f:
            file_data = json.load(f)

        # Build payload in the exact API shape.
        # If file already has {"date": ..., "data": [...]}, send it directly.
        if isinstance(file_data, dict) and "data" in file_data and "date" in file_data:
            payload = file_data
            payload["date"] = date_folder
        else:
            payload = {
                "date": date_folder,
                "data": file_data
            }

        # Push to API
        response = requests.post(API_URL, json=payload, timeout=30)

        if response.status_code == 200:
            body = response.text.strip()
            body_lower = body.lower()

            # Some APIs return 200 even for app-level failures. Check body text too.
            if any(word in body_lower for word in ["error", "failed", "invalid", "not inserted"]):
                print(f"❌ {date_folder}: Server rejected data -> {body[:180]}")
                error_count += 1
            else:
                print(f"✅ {date_folder}: Successfully pushed -> {body[:120]}")
                success_count += 1
        else:
            print(f"❌ {date_folder}: API returned status {response.status_code} -> {response.text[:180]}")
            error_count += 1
    
    except json.JSONDecodeError as e:
        print(f"❌ {date_folder}: Invalid JSON - {e}")
        error_count += 1
    except Exception as e:
        print(f"❌ {date_folder}: Error - {e}")
        error_count += 1

print(f"\n--- Summary ---")
print(f"Successfully pushed: {success_count}")
print(f"Errors: {error_count}")
