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
import re
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
            '--days-back',
            type=int,
            default=0,
            choices=[0, 1, 2, 3, 4],
            help='Which report link to fetch: 0=today, 1=previous_day1, 2=previous_day2, 3=previous_day3, 4=previous_day4'
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

    def extract_report_date_from_pdf(self, file_path):
        """Read observation/report date directly from PDF text."""
        date_patterns = [
            r"OF\s+DATE\s*[:\-]?\s*(\d{1,2}[-./]\d{1,2}[-./]\d{4})",
            r"DATE\s*[:\-]?\s*(\d{1,2}[-./]\d{1,2}[-./]\d{4})",
        ]

        with pdfplumber.open(file_path) as pdf:
            max_pages = min(len(pdf.pages), 8)
            for i in range(max_pages):
                text = pdf.pages[i].extract_text() or ""
                upper_text = text.upper()

                for pattern in date_patterns:
                    match = re.search(pattern, upper_text)
                    if not match:
                        continue

                    date_str = match.group(1).replace(".", "-").replace("/", "-")
                    for fmt in ("%d-%m-%Y", "%d-%m-%y"):
                        try:
                            return datetime.strptime(date_str, fmt).date()
                        except ValueError:
                            continue

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
    def download_pdf(self, file_path, days_back=0):
        base = "https://mausam.imd.gov.in/chennai/mcdata/"

        urls = [
    ("today", base + "daily_weather_report.pdf", 0),
    ("previous_day1", base + "previous_day1.pdf", 1),
    ("previous_day2", base + "previous_day2.pdf", 2),
    ("previous_day3", base + "previous_day3.pdf", 3),
    ("previous_day4", base + "previous_day4.pdf", 4),
]

        if days_back < 0 or days_back >= len(urls):
            self.stdout.write(self.style.ERROR("❌ days-back must be between 0 and 4"))
            return False, None

        label, url, day_offset = urls[days_back]

        try:
            self.stdout.write(f"🌐 Trying {label}: {url}")

            response = requests.get(url, timeout=20)

            if response.status_code != 200:
                self.stdout.write(self.style.WARNING(f"⚠️ {label} not available"))
                return False, None

            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower():
                self.stdout.write(self.style.WARNING(f"⚠️ Not a valid PDF ({label})"))
                return False, None

            # Save file
            with open(file_path, "wb") as f:
                f.write(response.content)

            # Verify file size
            file_size = os.path.getsize(file_path)
            if file_size < 5000:
                self.stdout.write(self.style.WARNING(f"⚠️ File too small ({label})"))
                return False, None

            self.stdout.write(self.style.SUCCESS(f"✅ Valid PDF downloaded ({label})"))
            self.stdout.write(f"📦 File size: {file_size} bytes")

            # Source of truth: observation date printed inside the PDF.
            parsed_report_date = self.extract_report_date_from_pdf(file_path)
            fallback_report_date = (datetime.now() - timedelta(days=day_offset)).date()

            if parsed_report_date:
                self.stdout.write(f"📅 Report date from PDF: {parsed_report_date}")
                report_date = parsed_report_date
            else:
                self.stdout.write(self.style.WARNING("⚠️ Could not parse report date from PDF, using fallback offset"))
                report_date = fallback_report_date

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
    # -----------------------------
# MAIN
# -----------------------------
    def handle(self, *args, **options):

        self.stdout.write("🚀 Starting IMD Data Fetch...")

        base_dir = os.getcwd()

        # ✅ DEFAULT OR USER INPUT
        days_back = options.get("days_back")

        if days_back is None:
            days_back = 0   # default = today
            self.stdout.write("📅 Running for TODAY (days-back: 0)")
        else:
            days_back = int(days_back)
            self.stdout.write(f"📅 Running for days-back: {days_back}")

        # temp path
        temp_file_path = os.path.join(base_dir, f"temp_weather_{days_back}.pdf")

        self.stdout.write("📥 Downloading PDF...")

        success, report_date = self.download_pdf(temp_file_path, days_back)

        if not success:
            self.stdout.write(self.style.ERROR("❌ No PDF available"))
            return

        if not report_date:
            self.stdout.write(
                self.style.ERROR("❌ Could not determine report date → Skipping")
            )
            return

        self.stdout.write(f"📅 Report Date: {report_date}")

        # ✅ Folder using actual report date
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
            return

        has_valid_cluster_data = any(
            row["maximum_past_24hrs"] is not None or row["minimum_past_24hrs"] is not None
            for row in cluster_result
        )

        if not has_valid_cluster_data:
            self.stdout.write(
                self.style.ERROR(
                    "❌ All cluster values are null. Skipping DB save to avoid bad rows."
                )
            )
            return

        self.stdout.write("💾 Saving to DB...")
        self.save_to_db(cluster_result, report_date)

        self.stdout.write(self.style.SUCCESS("✅ DONE - Data inserted successfully"))