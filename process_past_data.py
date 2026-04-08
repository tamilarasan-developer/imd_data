#!/usr/bin/env python
"""
Process past PDF data from past_pdf folder.
Extracts temperature data and saves to DB with -1 day delta.
Example: 20260201Daily.pdf -> stored as 2026-01-31
"""

import os
import json
import sys
import argparse
from datetime import datetime, timedelta
import pdfplumber
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path


# ==================== CONFIG ====================
PAST_PDF_DIR = os.path.join(os.getcwd(), "past_pdf")
OUTPUT_BASE_DIR = os.path.join(os.getcwd(), "Download")


# ==================== UTILITIES ====================
def clean_value(v):
    """Convert string to float, return None if invalid."""
    if v is None:
        return None

    v = str(v).strip()

    if v in ["NA", "--", "-", ""]:
        return None

    try:
        return float(v)
    except:
        return None


# ==================== DATABASE ====================
def push_cluster_data_to_db(cluster_rows, report_date):
    """Insert cluster data into database."""
    print(f"🔌 Connecting to DB for date {report_date}...")

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
        print(f"❌ Insert failed: {error}")
        raise


# ==================== PDF PROCESSING ====================
def find_temperature_table(pdf):
    """Find temperature table in PDF (new layout)."""
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


def find_legacy_temperature_table(pdf):
    """Find temperature table in PDF (legacy layout)."""
    for page_index in [3, 4]:
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


def extract_temperature_rows(table):
    """Extract station temperature data from table."""
    result = []

    for row in table[5:]:
        try:
            station = str(row[0]).replace("\n", "").strip()
            max_24hr = clean_value(row[1])
            min_24hr = clean_value(row[3])

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


def extract_data_from_pdf(file_path):
    """Extract temperature data from PDF."""
    with pdfplumber.open(file_path) as pdf:
        table = find_temperature_table(pdf)
        layout = "new"

        if table is None:
            table = find_legacy_temperature_table(pdf)
            layout = "legacy"

        if table is None:
            raise Exception("No temperature table found in PDF")

        print(f"  📘 Using {layout} PDF layout")
        return extract_temperature_rows(table)


# ==================== CLUSTERING ====================
def calculate_clusters(result):
    """Calculate cluster averages from station data."""
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


# ==================== MAIN PROCESSING ====================
def process_pdf_file(pdf_path, filename):
    """Process a single PDF file."""
    print(f"\n📄 Processing: {filename}")

    # Extract date from filename: 20260201Daily.pdf -> 2026-02-01
    try:
        date_str = filename[:8]  # Get YYYYMMDD
        file_date = datetime.strptime(date_str, "%Y%m%d").date()
    except:
        print(f"  ❌ Could not parse date from filename: {filename}")
        return False

    # Apply -1 day delta
    report_date = file_date - timedelta(days=1)
    print(f"  📅 File date: {file_date} → Store as: {report_date} (delta -1 day)")

    # Create output folder
    output_folder = os.path.join(OUTPUT_BASE_DIR, str(report_date))
    os.makedirs(output_folder, exist_ok=True)

    try:
        # Extract data
        print(f"  📊 Extracting data...")
        result = extract_data_from_pdf(pdf_path)

        if not result:
            print(f"  ⚠️ No station data extracted")
            return False

        # Calculate clusters
        print(f"  📈 Calculating clusters...")
        cluster_result = calculate_clusters(result)

        # Save JSON files
        cluster_json_path = os.path.join(output_folder, "cluster_temperature.json")
        with open(cluster_json_path, "w") as f:
            json.dump({"date": str(report_date), "data": cluster_result}, f, indent=4)

        temperature_json_path = os.path.join(output_folder, "temperature_24hrs.json")
        with open(temperature_json_path, "w") as f:
            json.dump(result, f, indent=4)

        print(f"  ✅ JSON saved to {output_folder}")

        # Push to database
        print(f"  💾 Pushing to database...")
        push_cluster_data_to_db(cluster_result, report_date)

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Main processing loop."""
    parser = argparse.ArgumentParser(
        description="Process past PDF data for IMD Chennai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process_past_data.py                    # Process all months
  python process_past_data.py --month "Jan 2026"  # Process only January
  python process_past_data.py --month "Feb 2026"  # Process only February
  python process_past_data.py --month "Mar 2026"  # Process only March
        """
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Specific month to process (e.g., 'Jan 2026', 'Feb 2026', 'Mar 2026')"
    )
    
    args = parser.parse_args()

    print("=" * 70)
    print("🚀 Past Data Processing Script")
    print("=" * 70)
    print(f"📁 Source: {PAST_PDF_DIR}")
    print(f"📁 Output: {OUTPUT_BASE_DIR}")
    if args.month:
        print(f"📅 Processing month: {args.month}")
    else:
        print(f"📅 Processing: All months")
    print()

    if not os.path.isdir(PAST_PDF_DIR):
        print(f"❌ Directory not found: {PAST_PDF_DIR}")
        return

    # Collect all PDF files
    all_pdfs = []
    for month_folder in sorted(os.listdir(PAST_PDF_DIR)):
        month_path = os.path.join(PAST_PDF_DIR, month_folder)
        if not os.path.isdir(month_path):
            continue

        # Filter by month if specified
        if args.month and month_folder != args.month:
            continue

        for filename in sorted(os.listdir(month_path)):
            if filename.endswith(".pdf"):
                all_pdfs.append((month_path, filename))

    if not all_pdfs:
        if args.month:
            print(f"❌ No PDF files found for month: {args.month}")
            print(f"   Available months:")
            for month_folder in sorted(os.listdir(PAST_PDF_DIR)):
                month_path = os.path.join(PAST_PDF_DIR, month_folder)
                if os.path.isdir(month_path):
                    print(f"     - {month_folder}")
        else:
            print("❌ No PDF files found")
        return

    print(f"📋 Found {len(all_pdfs)} PDF files to process\n")

    # Process each PDF
    success_count = 0
    error_count = 0

    for month_path, filename in all_pdfs:
        pdf_path = os.path.join(month_path, filename)
        if process_pdf_file(pdf_path, filename):
            success_count += 1
        else:
            error_count += 1

    # Summary
    print("\n" + "=" * 70)
    print("📊 Processing Summary")
    print("=" * 70)
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {error_count}")
    print(f"📊 Total: {len(all_pdfs)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
