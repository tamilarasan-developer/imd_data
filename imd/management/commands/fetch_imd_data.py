# import os
# import requests
# import json
# from datetime import datetime
# import pdfplumber

# from django.core.management.base import BaseCommand
# from django.utils.timezone import now

# from imd.models import imd_data


# class Command(BaseCommand):
#     help = "Fetch IMD Chennai data, process and store in DB"

#     # -----------------------------
#     # Clean value
#     # -----------------------------
#     def clean_value(self, v):
#         if v is None:
#             return None

#         v = str(v).strip()

#         if v in ["NA", "--", "-", ""]:
#             return None

#         try:
#             return float(v)
#         except:
#             return None

#     def find_temperature_table(self, pdf):
#         for page in pdf.pages:
#             tables = page.extract_tables()
#             for table in tables:
#                 if not table:
#                     continue

#                 header_text = " ".join(
#                     str(cell or "") for row in table[:5] for cell in row
#                 ).lower()

#                 if "stations" in header_text and "temperature" in header_text:
#                     return table

#         return None

#     def find_legacy_temperature_table(self, pdf):
#         for page_index in [3, 4]:
#             if len(pdf.pages) <= page_index:
#                 continue

#             tables = pdf.pages[page_index].extract_tables()
#             for table in tables:
#                 if not table:
#                     continue

#                 header_text = " ".join(
#                     str(cell or "") for row in table[:5] for cell in row
#                 ).lower()

#                 if "stations" in header_text and "temperature" in header_text:
#                     return table

#         return None

#     def extract_temperature_rows(self, table):
#         result = []

#         for row in table[5:]:
#             try:
#                 station = str(row[0]).replace("\n", "").strip()
#                 max_24hr = self.clean_value(row[1])
#                 min_24hr = self.clean_value(row[3])

#                 if station in ["", "None"]:
#                     continue

#                 if max_24hr is None and min_24hr is None:
#                     continue

#                 result.append({
#                     "station": station,
#                     "max": max_24hr,
#                     "min": min_24hr
#                 })
#             except:
#                 continue

#         return result

#     # -----------------------------
#     # Download PDF
#     # -----------------------------
#     def download_pdf(self, file_path):
#         url = "https://mausam.imd.gov.in/chennai/mcdata/daily_weather_report.pdf"

#         try:
#             response = requests.get(url, timeout=20)
#             response.raise_for_status()

#             with open(file_path, "wb") as f:
#                 f.write(response.content)

#             return True

#         except Exception as e:
#             self.stdout.write(self.style.ERROR(f"❌ Download failed: {e}"))
#             return False

#     # -----------------------------
#     # Extract table
#     # -----------------------------
#     def extract_data(self, file_path):
#         with pdfplumber.open(file_path) as pdf:
#             table = self.find_temperature_table(pdf)
#             layout = "new"

#             if table is None:
#                 table = self.find_legacy_temperature_table(pdf)
#                 layout = "legacy"

#             if table is None:
#                 raise Exception("No temperature table found in PDF")

#             self.stdout.write(f"📘 Using {layout} PDF layout")

#             return self.extract_temperature_rows(table)

#     # -----------------------------
#     # Cluster calculation
#     # -----------------------------
#     def calculate_clusters(self, result):
#         clusters = {
#             "CHENNAI": ["Chennai", "Chennai_AP"],
#             "VILLUPURAM": ["Parangipettai", "Cuddalore", "Puducherry"],
#             "VELLORE": ["Vellore", "Thirupattur"],
#             "ERODE": ["Erode", "Salem", "Namakkal", "Dharmapuri"],
#             "TRICHY": [
#                 "Tiruchirappalli_AP",
#                 "Thanjavur",
#                 "KarurParamathi",
#                 "Nagapattinam",
#                 "Adiramapattinam",
#                 "Tondi"
#             ],
#             "COIMBATORE": ["Coimbatore_AP"],
#             "MADURAI": ["Madurai_City", "Madurai_AP"],
#             "TIRUNELVELI": ["Thoothukudi", "Kanyakumari", "Pamban"]
#         }

#         cluster_result = []

#         for cluster_name, stations in clusters.items():
#             max_vals, min_vals = [], []

#             for entry in result:
#                 if entry["station"] in stations:
#                     if entry["max"] is not None:
#                         max_vals.append(entry["max"])
#                     if entry["min"] is not None:
#                         min_vals.append(entry["min"])

#             if max_vals and min_vals:
#                 max_avg = round(sum(max_vals) / len(max_vals), 2)
#                 min_avg = round(sum(min_vals) / len(min_vals), 2)
#                 avg = round((max_avg + min_avg) / 2, 2)
#             else:
#                 max_avg = min_avg = avg = None

#             cluster_result.append({
#                 "cluster": cluster_name,
#                 "maximum_past_24hrs": max_avg,
#                 "minimum_past_24hrs": min_avg,
#                 "average": avg
#             })

#         return cluster_result

#     # -----------------------------
#     # Save to DB
#     # -----------------------------
#     def save_to_db(self, cluster_result, report_date):
#         for row in cluster_result:
#             imd_data.objects.update_or_create(
#                 date=report_date,
#                 cluster=row["cluster"],
#                 defaults={
#                     "maximum_past_24hrs": row["maximum_past_24hrs"],
#                     "minimum_past_24hrs": row["minimum_past_24hrs"],
#                     "average": row["average"],
#                     "created_at": now()
#                 }
#             )

#     # -----------------------------
#     # MAIN FUNCTION
#     # -----------------------------
#     def handle(self, *args, **kwargs):

#         self.stdout.write("🚀 Starting IMD Data Fetch...")

#         today = datetime.now().strftime("%Y-%m-%d")

#         base_dir = os.getcwd()
#         folder_path = os.path.join(base_dir, "Download", today)
#         os.makedirs(folder_path, exist_ok=True)

#         file_path = os.path.join(folder_path, "daily_weather_report.pdf")

#         self.stdout.write("📥 Downloading PDF...")
#         if not self.download_pdf(file_path):
#             return

#         self.stdout.write("📊 Extracting data...")
#         try:
#             result = self.extract_data(file_path)
#         except Exception as e:
#             self.stdout.write(self.style.ERROR(f"❌ Extraction failed: {e}"))
#             return

#         self.stdout.write("📈 Calculating clusters...")
#         cluster_result = self.calculate_clusters(result)

#         # Save JSON (optional)
#         cluster_json_path = os.path.join(folder_path, "cluster_temperature.json")
#         with open(cluster_json_path, "w") as f:
#             json.dump({"date": today, "data": cluster_result}, f, indent=4)

#         temperature_json_path = os.path.join(folder_path, "temperature_24hrs.json")
#         with open(temperature_json_path, "w") as f:
#             json.dump(result, f, indent=4)

#         if not result:
#             self.stdout.write(self.style.WARNING("⚠️ No station rows were extracted from the PDF"))

#         self.stdout.write("💾 Saving to DB...")
#         report_date = datetime.strptime(today, "%Y-%m-%d").date()

#         self.save_to_db(cluster_result, report_date)

#         self.stdout.write(self.style.SUCCESS("✅ DONE - Data inserted successfully"))





















import os
import requests
import json
from datetime import datetime, timedelta
import pdfplumber

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from imd.models import imd_data


class Command(BaseCommand):
    help = "Fetch IMD Chennai data, process and store in DB"

    # -----------------------------
    # ARGUMENT
    # -----------------------------
    def add_arguments(self, parser):
        parser.add_argument(
            '--yesterday',
            action='store_true',
            help='Fetch only yesterday data'
        )

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
    # Find table
    # -----------------------------
    def find_temperature_table(self, pdf):
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                header_text = " ".join(
                    str(cell or "") for row in table[:5] for cell in row
                ).lower()

                if "stations" in header_text and "temperature" in header_text:
                    return table

        return None

    def find_legacy_temperature_table(self, pdf):
        for page_index in [3, 4]:
            if len(pdf.pages) <= page_index:
                continue

            tables = pdf.pages[page_index].extract_tables()
            for table in tables:
                if not table:
                    continue

                header_text = " ".join(
                    str(cell or "") for row in table[:5] for cell in row
                ).lower()

                if "stations" in header_text and "temperature" in header_text:
                    return table

        return None

    # -----------------------------
    # Extract rows
    # -----------------------------
    def extract_temperature_rows(self, table):
        result = []

        for row in table[5:]:
            try:
                station = str(row[0]).replace("\n", "").strip()
                max_24hr = self.clean_value(row[1])
                min_24hr = self.clean_value(row[3])

                if station in ["", "None"]:
                    continue

                if max_24hr is None and min_24hr is None:
                    continue

                result.append({
                    "station": station,
                    "max": max_24hr,
                    "min": min_24hr
                })
            except:
                continue

        return result

    # -----------------------------
    # Download PDF (FINAL)
    # -----------------------------
    def download_pdf(self, file_path, force_yesterday=False):
        base = "https://mausam.imd.gov.in/chennai/mcdata/"

        if force_yesterday:
            urls = [("yesterday", base + "previous_day1.pdf", 1)]
        else:
            urls = [
                ("today", base + "previous_day.pdf", 0),
                ("yesterday", base + "previous_day1.pdf", 1),
            ]

        for label, url, day_offset in urls:
            try:
                self.stdout.write(f"🌐 Trying {label}: {url}")

                response = requests.get(url, timeout=20)

                if response.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"⚠️ {label} not available"))
                    continue

                content_type = response.headers.get("Content-Type", "")
                if "pdf" not in content_type.lower():
                    self.stdout.write(self.style.WARNING(f"⚠️ Not a valid PDF ({label})"))
                    continue

                # Save file
                with open(file_path, "wb") as f:
                    f.write(response.content)

                # Verify file size
                file_size = os.path.getsize(file_path)
                if file_size < 5000:
                    self.stdout.write(self.style.WARNING(f"⚠️ File too small ({label})"))
                    continue

                self.stdout.write(self.style.SUCCESS(f"✅ Valid PDF downloaded ({label})"))
                self.stdout.write(f"📦 File size: {file_size} bytes")

                report_date = (datetime.now() - timedelta(days=day_offset)).date()

                return True, report_date

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ {label} failed: {e}"))

        return False, None

    # -----------------------------
    # Extract data
    # -----------------------------
    def extract_data(self, file_path):
        with pdfplumber.open(file_path) as pdf:
            table = self.find_temperature_table(pdf)
            layout = "new"

            if table is None:
                table = self.find_legacy_temperature_table(pdf)
                layout = "legacy"

            if table is None:
                raise Exception("No temperature table found in PDF")

            self.stdout.write(f"📘 Using {layout} PDF layout")

            return self.extract_temperature_rows(table)

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
    # MAIN
    # -----------------------------
    def handle(self, *args, **options):

        force_yesterday = options.get("yesterday")

        self.stdout.write("🚀 Starting IMD Data Fetch...")

        base_dir = os.getcwd()

        # temp path first
        temp_file_path = os.path.join(base_dir, "temp_weather.pdf")

        self.stdout.write("📥 Downloading PDF...")

        success, report_date = self.download_pdf(temp_file_path, force_yesterday)

        if not success:
            self.stdout.write(self.style.ERROR("❌ No PDF available"))
            return

        # ✅ Correct folder using actual date
        folder_path = os.path.join(base_dir, "Download", str(report_date))
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, "daily_weather_report.pdf")

        # Move temp file
        os.rename(temp_file_path, file_path)

        self.stdout.write(f"📁 Saved PDF at: {file_path}")

        self.stdout.write("📊 Extracting data...")
        try:
            result = self.extract_data(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Extraction failed: {e}"))
            return

        self.stdout.write("📈 Calculating clusters...")
        cluster_result = self.calculate_clusters(result)

        # Save JSON
        try:
            cluster_json_path = os.path.join(folder_path, "cluster_temperature.json")
            with open(cluster_json_path, "w") as f:
                json.dump({"date": str(report_date), "data": cluster_result}, f, indent=4)

            temperature_json_path = os.path.join(folder_path, "temperature_24hrs.json")
            with open(temperature_json_path, "w") as f:
                json.dump(result, f, indent=4)

            self.stdout.write(self.style.SUCCESS(f"✅ JSON saved in {folder_path}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ JSON save failed: {e}"))

        if not result:
            self.stdout.write(self.style.WARNING("⚠️ No station rows extracted"))

        self.stdout.write("💾 Saving to DB...")
        self.save_to_db(cluster_result, report_date)

        self.stdout.write(self.style.SUCCESS("✅ DONE - Data inserted successfully"))