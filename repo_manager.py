import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

REPOS_DB = DATA_DIR / "repos.db"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_repos_connection():
    conn = sqlite3.connect(REPOS_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_repos_db():
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL
                CHECK (status IN ('Running', 'Completed', 'Failed')),
            result_db_path TEXT,
            file_count INTEGER,
            high_risk INTEGER,
            medium_risk INTEGER,
            low_risk INTEGER,
            informational INTEGER,
            error_summary TEXT,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        )
        """
    )

    # Add columns for databases created by earlier versions.
    existing_columns = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(analysis_runs)").fetchall()
    }

    required_columns = {
        "raw_records": "INTEGER",
        "clean_records": "INTEGER",
        "skipped_bots": "INTEGER",
        "skipped_files": "INTEGER",
        "skipped_deleted": "INTEGER",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            cur.execute(
                f"ALTER TABLE analysis_runs ADD COLUMN {column_name} {column_type}"
            )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analysis_runs_repo_started
        ON analysis_runs(repo_id, started_at DESC)
        """
    )

    conn.commit()
    conn.close()

def get_or_create_repo(repo_path: str) -> dict:
    repo_path = str(Path(repo_path).resolve())

    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, path, name, created_at FROM repos WHERE path = ?",
        (repo_path,),
    )
    row = cur.fetchone()

    if row:
        conn.close()
        return dict(row)

    name = Path(repo_path).name or repo_path

    cur.execute(
        """
        INSERT INTO repos (path, name, created_at)
        VALUES (?, ?, ?)
        """,
        (repo_path, name, utc_now_iso()),
    )
    conn.commit()

    repo_id = cur.lastrowid
    cur.execute(
        "SELECT id, path, name, created_at FROM repos WHERE id = ?",
        (repo_id,),
    )
    row = cur.fetchone()
    conn.close()

    return dict(row)


def list_repos():
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, path, name, created_at
        FROM repos
        ORDER BY created_at DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_repo_by_id(repo_id: int) -> dict | None:
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, path, name, created_at
        FROM repos
        WHERE id = ?
        """,
        (repo_id,),
    )
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def create_analysis_run(repo_id: int) -> int:
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM analysis_runs
        WHERE repo_id = ? AND status = 'Running'
        LIMIT 1
        """,
        (repo_id,),
    )
    running = cur.fetchone()

    if running:
        conn.close()
        raise RuntimeError(
            "An analysis is already running for this repository."
        )

    cur.execute(
        """
        INSERT INTO analysis_runs (repo_id, started_at, status)
        VALUES (?, ?, 'Running')
        """,
        (repo_id, utc_now_iso()),
    )

    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    return run_id


def complete_analysis_run(
    run_id: int,
    result_db_path: str,
    summary: dict | None = None,
    file_count: int | None = None,
    risk_counts: dict | None = None,
):
    summary = summary or {}
    risk_counts = risk_counts or {}

    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE analysis_runs
        SET completed_at = ?,
            status = 'Completed',
            result_db_path = ?,
            raw_records = ?,
            clean_records = ?,
            skipped_bots = ?,
            skipped_files = ?,
            skipped_deleted = ?,
            file_count = ?,
            high_risk = ?,
            medium_risk = ?,
            low_risk = ?,
            informational = ?,
            error_summary = NULL
        WHERE id = ?
        """,
        (
            utc_now_iso(),
            str(Path(result_db_path).resolve()),
            summary.get("raw_records"),
            summary.get("clean_records"),
            summary.get("skipped_bots"),
            summary.get("skipped_files"),
            summary.get("skipped_deleted"),
            file_count,
            risk_counts.get("High"),
            risk_counts.get("Medium"),
            risk_counts.get("Low"),
            risk_counts.get("Informational"),
            run_id,
        ),
    )

    conn.commit()
    conn.close()


def fail_analysis_run(run_id: int, error_summary: str):
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE analysis_runs
        SET completed_at = ?,
            status = 'Failed',
            error_summary = ?
        WHERE id = ?
        """,
        (utc_now_iso(), error_summary[:1000], run_id),
    )

    conn.commit()
    conn.close()


def list_analysis_runs(repo_id: int, limit: int | None = None):
    conn = get_repos_connection()
    cur = conn.cursor()

    sql = """
        SELECT *
        FROM analysis_runs
        WHERE repo_id = ?
        ORDER BY started_at DESC, id DESC
    """
    params = [repo_id]

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_analysis_run(run_id: int):
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM analysis_runs WHERE id = ?",
        (run_id,),
    )
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def list_repos_with_latest_run():
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            r.id,
            r.path,
            r.name,
            r.created_at,
            latest.id AS latest_run_id,
            latest.started_at AS last_started_at,
            latest.completed_at AS last_completed_at,
            latest.status AS latest_status,
            latest.file_count AS latest_file_count,
            latest.high_risk AS latest_high_risk,
            latest.medium_risk AS latest_medium_risk,
            latest.low_risk AS latest_low_risk,
            latest.informational AS latest_informational,
            latest.error_summary AS latest_error_summary
        FROM repos AS r
        LEFT JOIN analysis_runs AS latest
            ON latest.id = (
                SELECT ar.id
                FROM analysis_runs AS ar
                WHERE ar.repo_id = r.id
                ORDER BY ar.started_at DESC, ar.id DESC
                LIMIT 1
            )
        ORDER BY COALESCE(latest.started_at, r.created_at) DESC
        """
    )

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]