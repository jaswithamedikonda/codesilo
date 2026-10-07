import subprocess
from pathlib import PurePosixPath


BOT_KEYWORDS = {
    "dependabot",
    "renovate",
    "github-actions",
    "gitlab-bot",
    "jenkins",
}

EXCLUDED_DIRECTORY_NAMES = {
    ".github",
    "docs",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "__pycache__",
}

EXCLUDED_FILE_NAMES = {
    "readme",
    "readme.md",
    "readme.rst",
    "changelog",
    "changelog.md",
    "changelog.rst",
    "changes",
    "changes.md",
    "notice",
    "license",
    "copying",
    "copyright",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
}

EXCLUDED_EXTENSIONS = {
    ".md",
    ".rst",
    ".txt",

    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".ai",
    ".tif",
    ".tiff",

    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".avi",
    ".mov",
    ".webm",
    
    ".zip",
    ".pdf",
    ".map",
}

EXCLUDED_FILE_SUFFIXES = {
    ".min.js",
}


def is_bot(author_name, author_email):
    identity = f"{author_name} {author_email}".lower()

    if "[bot]" in identity:
        return True

    return any(keyword in identity for keyword in BOT_KEYWORDS)


def is_excluded_file(file_path):
    normalized_path = file_path.replace("\\", "/").lower()
    path = PurePosixPath(normalized_path)

    if any(part in EXCLUDED_DIRECTORY_NAMES for part in path.parts):
        return True

    if path.name in EXCLUDED_FILE_NAMES:
        return True

    if path.name.endswith(".lock"):
        return True

    if path.suffix in EXCLUDED_EXTENSIONS:
        return True

    if any(path.name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES):
        return True

    return False


def get_current_files(repo_path):
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )

    return {
        line.replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def clean_records(records, repo_path):
    current_files = get_current_files(repo_path)

    cleaned_records = []

    skipped_bots = 0
    skipped_files = 0
    skipped_deleted = 0

    for record in records:
        author_name = record["author_name"]
        author_email = record["author_email"]
        file_path = record["file_path"].replace("\\", "/")

        if is_bot(author_name, author_email):
            skipped_bots += 1
            continue

        if is_excluded_file(file_path):
            skipped_files += 1
            continue

        if file_path not in current_files:
            skipped_deleted += 1
            continue

        record["file_path"] = file_path
        cleaned_records.append(record)

    summary = {
        "raw_records": len(records),
        "clean_records": len(cleaned_records),
        "skipped_bots": skipped_bots,
        "skipped_files": skipped_files,
        "skipped_deleted": skipped_deleted,
    }

    return cleaned_records, summary