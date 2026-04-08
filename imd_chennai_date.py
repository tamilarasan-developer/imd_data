import requests
import os
from datetime import datetime, timedelta
import pdfplumber
import json
import psycopg2
from psycopg2.extras import execute_values


# -----------------------------
# Function to clean values
# -----------------------------
def clean_value(v):
    if v is None:
        return None

    v = str(v).strip()

    if v in ["NA", "--", "-", ""]:
        return None

    try:
        return float(v)
    except:
        return None


# -----------------------------
# DB Push Function (UPDATED)
# -----------------------------
def push_cluster_data_to_db(cluster_rows, report_date):
    print("🔌 Connecting to DB...")

    db_config = {
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "LGEcbe@26"),
        "host": os.getenv("DB_HOST", "172.16.7.116"),
        "port": os.getenv("DB_PORT", "5432")
    }
  
    insert_sql = """
        INSERT INTO imd_data_chennai (
            date,
            cluster,
            maximum_past_24hrs,
            minimum_past_24hrs,
            average,
            created_at
        ) VALUES %s
        ON CONFLICT (date, cluster)
        DO UPDATE SET
            maximum_past_24hrs = EXCLUDED.maximum_past_24hrs,
            minimum_past_24hrs = EXCLUDED.minimum_past_24hrs,
            average = EXCLUDED.average,
            created_at = CURRENT_TIMESTAMP
    """

    rows = [
        (
            report_date,
            row["cluster"],
            row["maximum_past_24hrs"],
            row["minimum_past_24hrs"],
            row["average"],
            datetime.now()
        )
        for row in cluster_rows
    ]

    try:
        with psycopg2.connect(**db_config) as connection:
            with connection.cursor() as cursor:
                execute_values(cursor, insert_sql, rows)
        print("✅ Data inserted into imd_data_chennai")
    except Exception as error:
        print("❌ Insert failed:", error)
        raise


# -----------------------------
# Create "Download" folder
# -----------------------------
base_dir = os.getcwd()
download_dir = os.path.join(base_dir, "Download")
os.makedirs(download_dir, exist_ok=True)


# -----------------------------
# Create Date Folder (-1 day)
# -----------------------------
report_date_obj = (datetime.now() - timedelta(days=1)).date()
report_date_str = report_date_obj.strftime("%Y-%m-%d")

folder_path = os.path.join(download_dir, report_date_str)
os.makedirs(folder_path, exist_ok=True)

print("📁 Saving to:", folder_path)


# -----------------------------
# PDF URL
# -----------------------------
url = "https://mausam.imd.gov.in/chennai/mcdata/daily_weather_report.pdf"
file_path = os.path.join(folder_path, "daily_weather_report.pdf")


# -----------------------------
# Download PDF
# -----------------------------
response = requests.get(url)

if response.status_code == 200:
    with open(file_path, "wb") as f:
        f.write(response.content)
    print("✅ PDF downloaded successfully!")
else:
    print("❌ Download failed:", response.status_code)
    exit()


# -----------------------------
# Extract Data
# -----------------------------
result = []

with pdfplumber.open(file_path) as pdf:

    table = None

    if len(pdf.pages) > 3:
        tables = pdf.pages[3].extract_tables()
        if tables:
            table = tables[0]

    if table is None and len(pdf.pages) > 4:
        tables = pdf.pages[4].extract_tables()
        if tables:
            table = tables[0]

    if table is None:
        print(f"❌ No table found. Total pages: {len(pdf.pages)}")
        exit()

    for row in table[5:]:
        try:
            station = str(row[0]).replace("\n", "").strip()

            max_24hr = clean_value(row[1])
            min_24hr = clean_value(row[3])

            result.append({
                "station": station,
                "maximum_past_24hrs": max_24hr,
                "minimum_past_24hrs": min_24hr
            })
        except:
            continue


# -----------------------------
# Clusters
# -----------------------------
clusters = {
    "CHENNAI": ["Chennai", "Chennai_AP"],
    "VILLUPURAM": ["Parangipettai", "Cuddalore", "Puducherry"],
    "VELLORE": ["Vellore", "Thirupattur"],
    "ERODE": ["Erode", "Salem", "Namakkal", "Dharmapuri"],
    "TRICHY": [
        "Tiruchirappalli_AP",
        "Thanjavur",
        "KarurParamathi",
        "Nagapattinam",
        "Adiramapattinam",
        "Tondi"
    ],
    "COIMBATORE": ["Coimbatore_AP"],
    "MADURAI": ["Madurai_City", "Madurai_AP"],
    "TIRUNELVELI": ["Thoothukudi", "Kanyakumari", "Pamban"]
}


# -----------------------------
# Cluster Calculation
# -----------------------------
cluster_result = []

for cluster_name, stations in clusters.items():

    max_values = []
    min_values = []

    for entry in result:
        if entry["station"] in stations:

            if entry["maximum_past_24hrs"] is not None:
                max_values.append(entry["maximum_past_24hrs"])

            if entry["minimum_past_24hrs"] is not None:
                min_values.append(entry["minimum_past_24hrs"])

    if max_values and min_values:
        max_avg = round(sum(max_values) / len(max_values), 2)
        min_avg = round(sum(min_values) / len(min_values), 2)
        avg = round((max_avg + min_avg) / 2, 2)
    else:
        max_avg = None
        min_avg = None
        avg = None

    cluster_result.append({
        "cluster": cluster_name,
        "maximum_past_24hrs": max_avg,
        "minimum_past_24hrs": min_avg,
        "average": avg
    })


# -----------------------------
# Save JSON Files
# -----------------------------
cluster_json_path = os.path.join(folder_path, "cluster_temperature.json")
temperature_json_path = os.path.join(folder_path, "temperature_24hrs.json")

cluster_output = {
    "date": report_date_str,
    "data": cluster_result
}

with open(cluster_json_path, "w") as f:
    json.dump(cluster_output, f, indent=4)

with open(temperature_json_path, "w") as f:
    json.dump(result, f, indent=4)

print("✅ Cluster data saved:", cluster_json_path)
print("✅ Temperature data saved:", temperature_json_path)


# -----------------------------
# Push JSON data to DB (FINAL FIX)
# -----------------------------
print("🚀 Starting DB push...")

try:
    with open(cluster_json_path, "r") as f:
        json_data = json.load(f)

    cluster_rows = json_data["data"]

    print(f"📊 Rows to insert: {len(cluster_rows)}")

    push_cluster_data_to_db(
        cluster_rows,
        report_date_obj
    )

    print("✅ DB push completed!")

except Exception as e:
    print("❌ Failed to push JSON data to DB:", e)