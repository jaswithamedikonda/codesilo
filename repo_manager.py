import sqlite3
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

REPOS_DB = DATA_DIR / "repos.db"


def get_repos_connection():
    conn = sqlite3.connect(REPOS_DB)
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
    created_at = datetime.utcnow().isoformat()

    cur.execute(
        "INSERT INTO repos (path, name, created_at) VALUES (?, ?, ?)",
        (repo_path, name, created_at),
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
        "SELECT id, path, name, created_at FROM repos ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_repo_by_id(repo_id: int) -> dict | None:
    conn = get_repos_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, path, name, created_at FROM repos WHERE id = ?",
        (repo_id,),
    )
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None