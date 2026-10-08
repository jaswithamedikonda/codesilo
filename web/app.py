import os
import sys
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, send_file

# Make root modules importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics import get_file_concentration, get_top_files_by_activity
from export_csv import export_concentration_csv
from config import DATABASE_PATH

app = Flask(__name__)

# For now, use a global DB file at repo root.
# Later we can make this per-repo inside data/.
DB_PATH = ROOT / "codesilo.db"
os.makedirs(ROOT / "data", exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    repo_path = request.form.get("repo_path", "").strip()

    if not repo_path:
        return render_template(
            "index.html",
            error="Please enter a repository path.",
        )

    # TODO: validate repo_path, run Git parsing, populate DB
    # For now, just assume DB exists and go to dashboard.

    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    concentration_rows = get_file_concentration(limit=50)
    top_files = get_top_files_by_activity(limit=20)

    concentration = [dict(r) for r in concentration_rows]
    top = [dict(r) for r in top_files]

    total_files = len(concentration)
    high_risk = sum(1 for r in concentration if r["risk_level"] == "High")
    medium_risk = sum(1 for r in concentration if r["risk_level"] == "Medium")
    low_risk = sum(1 for r in concentration if r["risk_level"] == "Low")
    informational = sum(
        1 for r in concentration if r["risk_level"] == "Informational"
    )

    return render_template(
        "dashboard.html",
        concentration=concentration,
        top_files=top,
        total_files=total_files,
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        informational=informational,
    )


@app.route("/export")
def export():
    output_path = ROOT / "data" / "codesilo_concentration.csv"
    export_concentration_csv(str(output_path))
    return send_file(
        output_path,
        as_attachment=True,
        download_name="codesilo_concentration.csv",
    )


if __name__ == "__main__":
    app.run(debug=True)