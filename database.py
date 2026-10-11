import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_connection(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables(db_path: Path):
    connection = get_connection(db_path)
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            analyzed_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL,
            commit_hash TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_email TEXT NOT NULL,
            commit_date TEXT NOT NULL,
            UNIQUE(repository_id, commit_hash),
            FOREIGN KEY (repository_id)
                REFERENCES repositories(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS file_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commit_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            lines_added INTEGER NOT NULL,
            lines_deleted INTEGER NOT NULL,
            change_activity INTEGER NOT NULL,
            FOREIGN KEY (commit_id)
                REFERENCES commits(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_file_changes_path
        ON file_changes(file_path)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_commits_author_email
        ON commits(author_email)
        """
    )

    connection.commit()
    connection.close()


def save_analysis(repo_path, records, db_path: Path):
    create_tables(db_path)

    connection = get_connection(db_path)
    cursor = connection.cursor()

    repo_name = Path(repo_path).name
    analyzed_at = datetime.now().isoformat(timespec="seconds")

    cursor.execute(
        """
        INSERT INTO repositories (name, path, analyzed_at)
        VALUES (?, ?, ?)
        ON CONFLICT(path)
        DO UPDATE SET analyzed_at = excluded.analyzed_at
        """,
        (repo_name, repo_path, analyzed_at),
    )

    cursor.execute(
        "SELECT id FROM repositories WHERE path = ?",
        (repo_path,),
    )

    repository_id = cursor.fetchone()[0]

    cursor.execute(
        "DELETE FROM commits WHERE repository_id = ?",
        (repository_id,),
    )

    commit_id_by_hash = {}

    for record in records:
        commit_hash = record["commit_hash"]

        if commit_hash not in commit_id_by_hash:
            cursor.execute(
                """
                INSERT INTO commits (
                    repository_id,
                    commit_hash,
                    author_name,
                    author_email,
                    commit_date
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    repository_id,
                    commit_hash,
                    record["author_name"],
                    record["author_email"],
                    record["commit_date"],
                ),
            )

            commit_id_by_hash[commit_hash] = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO file_changes (
                commit_id,
                file_path,
                lines_added,
                lines_deleted,
                change_activity
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                commit_id_by_hash[commit_hash],
                record["file_path"],
                record["lines_added"],
                record["lines_deleted"],
                record["change_activity"],
            ),
        )

    connection.commit()
    connection.close()