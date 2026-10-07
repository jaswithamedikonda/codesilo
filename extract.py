import subprocess
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


if __name__ == "__main__":
    repository_path = r"C:/Users/jaswi/projects/practice-repo"

    raw_history = get_history(repository_path)

    cleaned_history, summary = clean_records(
        raw_history,
        repository_path
    )
    save_analysis(repository_path, cleaned_history)

    print("Cleaned records saved to codesilo.db")

    print("Cleaning summary")
    print("-" * 55)
    print(f"Raw file-change records: {summary['raw_records']}")
    print(f"Clean records kept: {summary['clean_records']}")
    print(f"Skipped bot records: {summary['skipped_bots']}")
    print(f"Skipped excluded files: {summary['skipped_files']}")
    print(f"Skipped deleted files: {summary['skipped_deleted']}")
    print("-" * 55)

    print("First 10 clean records")

    for record in cleaned_history[:10]:
        print(f"Author: {record['author_name']} <{record['author_email']}>")
        print(f"Date: {record['commit_date']}")
        print(f"File: {record['file_path']}")
        print(f"Added: {record['lines_added']}")
        print(f"Deleted: {record['lines_deleted']}")
        print(f"Change activity: {record['change_activity']}")
        print(f"Commit: {record['commit_hash']}")
        print("-" * 55)