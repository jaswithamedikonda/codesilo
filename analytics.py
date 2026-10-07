import sqlite3
from pathlib import Path


DATABASE_PATH = Path("codesilo.db")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_top_files_by_activity(limit=20):
    connection = get_connection()
    cursor = connection.cursor()

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
    connection.close()

    return rows


if __name__ == "__main__":
    top_files = get_top_files_by_activity()

    print("Top files by total recorded change activity")
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