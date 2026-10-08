import subprocess
from pathlib import Path, PurePosixPath

from cleaner import clean_records
from database import save_analysis


def get_history(repo_path):
    command = [
        "git",
        "log",
        "--no-merges",
        "--numstat",
        "--no-renames",
        "--pretty=format:@@%H|%ae|%an|%aI",
    ]

    result = subprocess.run(
        command,
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )

    records = []

    current_commit = None
    current_email = None
    current_name = None
    current_date = None

    for line in result.stdout.splitlines():
        if line.startswith("@@"):
            current_commit, current_email, current_name, current_date = (
                line[2:].split("|", 3)
            )

            current_email = current_email.lower()
            continue

        if not line.strip() or current_commit is None:
            continue

        parts = line.split("\t", 2)

        if len(parts) != 3:
            continue

        added, deleted, file_path = parts

        if added == "-" or deleted == "-":
            continue

        added = int(added)
        deleted = int(deleted)

        records.append(
            {
                "commit_hash": current_commit,
                "author_email": current_email,
                "author_name": current_name,
                "commit_date": current_date,
                "file_path": file_path,
                "lines_added": added,
                "lines_deleted": deleted,
                "change_activity": added + deleted,
            }
        )

    return records


def analyze_repo(repo_path: str, db_path: Path):
    raw_history = get_history(repo_path)

    cleaned_history, summary = clean_records(raw_history, repo_path)

    save_analysis(repo_path, cleaned_history, db_path)

    return summary