import os
import sys
from pathlib import Path

# Make root modules importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template, request, redirect, url_for, send_file
from web.suggestions import generate_repo_suggestions, generate_file_suggestion

print("Flask app module loaded")

from analytics import get_file_concentration, get_top_files_by_activity
from export_csv import export_concentration_csv
from repo_manager import (
    init_repos_db,
    get_or_create_repo,
    list_repos,
    get_repo_by_id,
)
from pipeline import analyze_repo

app = Flask(__name__)

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Ensure repos DB exists
init_repos_db()


def repo_db_path(repo_id: int) -> Path:
    return DATA_DIR / f"{repo_id}.db"


@app.route("/")
def index():
    repos = list_repos()
    return render_template("index.html", repos=repos)


@app.route("/analyze", methods=["POST"])
def analyze():
    repo_path = request.form.get("repo_path", "").strip()

    if not repo_path:
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Please enter a repository path.",
        )

    # Basic validation: path must exist and be a git repo
    if not Path(repo_path).is_dir():
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Repository path does not exist.",
        )

    git_dir = Path(repo_path) / ".git"
    if not git_dir.exists():
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Not a Git repository (no .git folder found).",
        )

    repo = get_or_create_repo(repo_path)
    repo_id = repo["id"]
    db_path = repo_db_path(repo_id)

    analyze_repo(repo_path, db_path)

    # Came from home page → back should go to home
    return redirect(url_for("dashboard", repo_id=repo_id, from_="home"))


@app.route("/analyze-sample", methods=["POST"])
def analyze_sample():
    sample_repo_path = request.form.get("sample_repo", "").strip()

    if not sample_repo_path:
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Please select a sample repository.",
        )

    if not Path(sample_repo_path).is_dir():
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Selected sample repository path does not exist.",
        )

    git_dir = Path(sample_repo_path) / ".git"
    if not git_dir.exists():
        repos = list_repos()
        return render_template(
            "index.html",
            repos=repos,
            error="Selected path is not a Git repository.",
        )

    repo = get_or_create_repo(sample_repo_path)
    repo_id = repo["id"]
    db_path = repo_db_path(repo_id)

    analyze_repo(sample_repo_path, db_path)

    # Came from home page (sample) → back should go to home
    return redirect(url_for("dashboard", repo_id=repo_id, from_="home"))


@app.route("/dashboard")
def dashboard():
    repo_id = request.args.get("repo_id")
    if not repo_id:
        repos = list_repos()
        return render_template("dashboard_empty.html", repos=repos)

    repo_id = int(repo_id)
    repo = get_repo_by_id(repo_id)
    if not repo:
        return "Repository not found", 404

    db_path = repo_db_path(repo_id)

    if not db_path.exists():
        repos = list_repos()
        return render_template(
            "dashboard_empty.html",
            repos=repos,
            message="This repository has not been analyzed yet.",
        )

    # Get ALL files, not just 50
    concentration_rows = get_file_concentration(db_path=db_path)  # no limit
    top_files = get_top_files_by_activity(limit=20, db_path=db_path)

    concentration = [dict(r) for r in concentration_rows]
    top = [dict(r) for r in top_files]

    # Generate per-file suggestions
    for row in concentration:
        row["suggestion"] = generate_file_suggestion(row)

    # Generate repo-level suggestions
    repo_suggestions = generate_repo_suggestions(concentration)

    total_files = len(concentration)
    high_risk = sum(
        1 for r in concentration
        if r.get("risk_level") == "High"
    )
    medium_risk = sum(
        1 for r in concentration
        if r.get("risk_level") == "Medium"
    )
    low_risk = sum(
        1 for r in concentration
        if r.get("risk_level") == "Low"
    )
    informational = sum(
        1 for r in concentration
        if r.get("risk_level") == "Informational"
    )

    return render_template(
        "dashboard.html",
        repo=repo,
        concentration=concentration,
        top_files=top,
        total_files=total_files,
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        informational=informational,
        repo_suggestions=repo_suggestions,
    )


@app.route("/export/<int:repo_id>")
def export(repo_id):
    db_path = repo_db_path(repo_id)
    if not db_path.exists():
        return "No data to export", 404

    output_path = DATA_DIR / f"codesilo_{repo_id}_concentration.csv"
    export_concentration_csv(str(output_path), db_path=db_path)

    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"codesilo_{repo_id}_concentration.csv",
    )


@app.route("/history")
def history():
    repos = list_repos()
    return render_template("history.html", repos=repos)


if __name__ == "__main__":
    app.run(debug=True)