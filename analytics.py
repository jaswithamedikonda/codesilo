import sqlite3
import re
from pathlib import Path

from config import IMPORTANT_PATH_KEYWORDS
from risk_engine import classify_risk

DATABASE_PATH = Path("codesilo.db")

def get_connection_for_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def tokenize_path(file_path):
    spaced_path = re.sub(
        "([a-z])([A-Z])",
        lambda m: m.group(1) + " " + m.group(2),
        file_path,
    )
    return re.split(r"[^a-z0-9]+", spaced_path.lower())

def is_potentially_important(file_path):
    tokens = tokenize_path(file_path)

    return any(
        token in IMPORTANT_PATH_KEYWORDS
        for token in tokens
    )

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_top_files_by_activity(limit=20, db_path=None):
    if db_path is None:
        raise ValueError("db_path must be provided")

    conn = get_connection_for_db(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            file_path,
            SUM(change_activity) AS total_change_activity,
            COUNT(*) AS change_count,
            COUNT(DISTINCT commit_id) AS distinct_commit_count
        FROM file_changes
        GROUP BY file_path
        ORDER BY total_change_activity DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    return rows

def get_file_concentration(limit=None, meaningful_threshold=10, db_path=None):
    if db_path is None:
        raise ValueError("db_path must be provided")

    conn = get_connection_for_db(db_path)
    cursor = conn.cursor()

    sql = """
        WITH contributor_activity AS (
            SELECT
                fc.file_path,
                c.author_name,
                c.author_email,
                SUM(fc.change_activity) AS contributor_activity
            FROM file_changes AS fc
            JOIN commits AS c
                ON fc.commit_id = c.id
            GROUP BY
                fc.file_path,
                c.author_name,
                c.author_email
        ),
        file_totals AS (
            SELECT
                file_path,
                SUM(change_activity) AS total_activity,
                COUNT(DISTINCT commit_id) AS change_count
            FROM file_changes
            GROUP BY file_path
        ),
        contributor_shares AS (
            SELECT
                ca.file_path,
                ca.author_name,
                ca.author_email,
                ca.contributor_activity,
                ft.total_activity,
                ft.change_count,
                ca.contributor_activity * 100.0 / ft.total_activity
                    AS activity_share
            FROM contributor_activity AS ca
            JOIN file_totals AS ft
                ON ca.file_path = ft.file_path
        ),
        file_contributor_counts AS (
            SELECT
                file_path,
                COUNT(*) AS total_contributor_count,
                COUNT(
                    CASE
                        WHEN activity_share >= ? THEN 1
                    END
                ) AS meaningful_contributor_count
            FROM contributor_shares
            GROUP BY file_path
        ),
        ranked_contributors AS (
            SELECT
                cs.file_path,
                cs.author_name,
                cs.author_email,
                cs.contributor_activity,
                cs.total_activity,
                cs.change_count,
                cs.activity_share,
                ROW_NUMBER() OVER (
                    PARTITION BY cs.file_path
                    ORDER BY cs.contributor_activity DESC
                ) AS contributor_rank
            FROM contributor_shares AS cs
        )
        SELECT
            rc.file_path,
            rc.author_name AS top_contributor,
            rc.author_email AS top_contributor_email,
            rc.contributor_activity AS top_contributor_activity,
            rc.total_activity,
            rc.change_count,
            fcc.total_contributor_count,
            fcc.meaningful_contributor_count,
            CASE
                WHEN rc.change_count >= 10 THEN 'Strong'
                WHEN rc.change_count >= 4 THEN 'Moderate'
                ELSE 'Weak'
            END AS evidence_strength,
            ROUND(rc.activity_share, 2) AS concentration_percentage
        FROM ranked_contributors AS rc
        JOIN file_contributor_counts AS fcc
            ON rc.file_path = fcc.file_path
        WHERE rc.contributor_rank = 1
        ORDER BY rc.total_activity DESC
    """

    params = [meaningful_threshold]

    if limit is not None:
        sql += "LIMIT ?"
        params.append(limit)

    cursor.execute(sql, params)

    rows = cursor.fetchall()
    conn.close()

    results = []

    for row in rows:
        result = dict(row)
        result["potentially_important"] = is_potentially_important(
            result["file_path"]
        )

        result["risk_level"] = classify_risk(
            result["concentration_percentage"],
            result["evidence_strength"],
            result["meaningful_contributor_count"],
            result["potentially_important"],
        )

        results.append(result)

    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="CodeSilo: knowledge-silo analysis"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of top files to show (default: 20)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export results to CSV instead of printing tables",
    )
    args = parser.parse_args()

    if args.csv:
        from export_csv import export_concentration_csv
        export_concentration_csv()
    else:
        top_files = get_top_files_by_activity(limit=args.limit)

        print("\nTop files by total recorded change activity")
        print("-" * 90)
        print(
            f"{'File path':<55}"
            f"{'Activity':>12}"
            f"{'Changes':>10}"
            f"{'Commits':>10}"
        )
        print("-" * 90)

        for row in top_files:
            print(
                f"{row['file_path']:<55}"
                f"{row['total_change_activity']:>12}"
                f"{row['change_count']:>10}"
                f"{row['distinct_commit_count']:>10}"
            )

        concentration_rows = get_file_concentration(limit=args.limit)

        print("\nTop contributor concentration by file")
        print("-" * 145)
        print(
            f"{'File path':<32} | "
            f"{'Top contributor':<22} | "
            f"{'Changes':>7} | "
            f"{'Meaningful':>10} | "
            f"{'Evidence':<10} | "
            f"{'Important':<9} | "
            f"{'Concentration':>13} | "
            f"{'Risk':<12}"
        )
        print("-" * 145)

        for row in concentration_rows:
            important_label = "Yes" if row["potentially_important"] else "No"

            print(
                f"{row['file_path']:<32} | "
                f"{row['top_contributor']:<22} | "
                f"{row['change_count']:>7} | "
                f"{row['meaningful_contributor_count']:>10} | "
                f"{row['evidence_strength']:<10} | "
                f"{important_label:<9} | "
                f"{row['concentration_percentage']:>12.2f}% | "
                f"{row['risk_level']:<12}"
            )