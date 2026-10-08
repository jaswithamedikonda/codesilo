import csv
from pathlib import Path

from analytics import get_file_concentration


def export_concentration_csv(output_path="codesilo_concentration.csv"):
    rows = get_file_concentration(limit=100)

    fieldnames = [
        "file_path",
        "top_contributor",
        "top_contributor_email",
        "top_contributor_activity",
        "change_count",
        "total_activity",
        "total_contributor_count",
        "meaningful_contributor_count",
        "evidence_strength",
        "concentration_percentage",
        "potentially_important",
        "risk_level",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

    print(f"Exported {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    export_concentration_csv()