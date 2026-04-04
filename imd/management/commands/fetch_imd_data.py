import os
import requests
import json
from datetime import datetime
import pdfplumber

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from imd.models import imd_data


class Command(BaseCommand):
    help = "Fetch IMD Chennai data, process and store in DB"

    # -----------------------------
    # Clean value
    # -----------------------------
    def clean_value(self, v):
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
    # Download PDF
    # -----------------------------
    def download_pdf(self, file_path):
        url = "https://mausam.imd.gov.in/chennai/mcdata/daily_weather_report.pdf"

        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)

            return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Download failed: {e}"))
            return False

    # -----------------------------
    # Extract table
    # -----------------------------
    def extract_data(self, file_path):
        result = []

        with pdfplumber.open(file_path) as pdf:
            table = None

            for page_index in [3, 4]:
                if len(pdf.pages) > page_index:
                    tables = pdf.pages[page_index].extract_tables()
                    if tables:
                        table = tables[0]
                        break

            if table is None:
                raise Exception("No table found in PDF")

            for row in table[5:]:
                try:
                    station = str(row[0]).replace("\n", "").strip()

                    result.append({
                        "station": station,
                        "max": self.clean_value(row[1]),
                        "min": self.clean_value(row[3])
                    })
                except:
                    continue

        return result

    # -----------------------------
    # Cluster calculation
    # -----------------------------
    def calculate_clusters(self, result):
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

        cluster_result = []

        for cluster_name, stations in clusters.items():
            max_vals, min_vals = [], []

            for entry in result:
                if entry["station"] in stations:
                    if entry["max"] is not None:
                        max_vals.append(entry["max"])
                    if entry["min"] is not None:
                        min_vals.append(entry["min"])

            if max_vals and min_vals:
                max_avg = round(sum(max_vals) / len(max_vals), 2)
                min_avg = round(sum(min_vals) / len(min_vals), 2)
                avg = round((max_avg + min_avg) / 2, 2)
            else:
                max_avg = min_avg = avg = None

            cluster_result.append({
                "cluster": cluster_name,
                "maximum_past_24hrs": max_avg,
                "minimum_past_24hrs": min_avg,
                "average": avg
            })

        return cluster_result

    # -----------------------------
    # Save to DB
    # -----------------------------
    def save_to_db(self, cluster_result, report_date):
        for row in cluster_result:
            imd_data.objects.update_or_create(
                date=report_date,
                cluster=row["cluster"],
                defaults={
                    "maximum_past_24hrs": row["maximum_past_24hrs"],
                    "minimum_past_24hrs": row["minimum_past_24hrs"],
                    "average": row["average"],
                    "created_at": now()
                }
            )

    # -----------------------------
    # MAIN FUNCTION
    # -----------------------------
    def handle(self, *args, **kwargs):

        self.stdout.write("🚀 Starting IMD Data Fetch...")

        today = datetime.now().strftime("%Y-%m-%d")

        base_dir = os.getcwd()
        folder_path = os.path.join(base_dir, "Download", today)
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, "daily_weather_report.pdf")

        self.stdout.write("📥 Downloading PDF...")
        if not self.download_pdf(file_path):
            return

        self.stdout.write("📊 Extracting data...")
        try:
            result = self.extract_data(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Extraction failed: {e}"))
            return

        self.stdout.write("📈 Calculating clusters...")
        cluster_result = self.calculate_clusters(result)

        # Save JSON (optional)
        cluster_json_path = os.path.join(folder_path, "cluster_temperature.json")
        with open(cluster_json_path, "w") as f:
            json.dump({"date": today, "data": cluster_result}, f, indent=4)

        self.stdout.write("💾 Saving to DB...")
        report_date = datetime.strptime(today, "%Y-%m-%d").date()

        self.save_to_db(cluster_result, report_date)

        self.stdout.write(self.style.SUCCESS("✅ DONE - Data inserted successfully"))