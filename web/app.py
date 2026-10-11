import shutil
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from analytics import get_file_concentration
from export_csv import export_concentration_csv
from pipeline import analyze_repo
from repo_manager import (
    complete_analysis_run,
    create_analysis_run,
    fail_analysis_run,
    get_analysis_run,
    get_or_create_repo,
    get_repo_by_id,
    init_repos_db,
    list_analysis_runs,
    list_repos,
    list_repos_with_latest_run,
)

app = Flask(__name__)

DATA_DIR = ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"
DATA_DIR.mkdir(exist_ok=True)
RUNS_DIR.mkdir(exist_ok=True)

init_repos_db()


def repo_db_path(repo_id: int) -> Path:
    """Latest-report database, retained for compatibility."""
    return DATA_DIR / f"{repo_id}.db"


def run_db_path(run_id: int) -> Path:
    """Unique database for one analysis run."""
    return RUNS_DIR / f"{run_id}.db"


def build_file_suggestion(row):
    """Choose a file-specific recommendation from its ownership evidence."""
    risk = row.get("risk_level", "Informational")
    evidence = row.get("evidence_strength", "Weak")
    meaningful = row.get("meaningful_contributor_count") or 0
    total_contributors = row.get("total_contributor_count") or 0
    concentration = row.get("concentration_percentage") or 0
    change_count = row.get("change_count") or 0
    important = bool(row.get("potentially_important"))

    # Not enough history for a confident ownership assessment.
    if evidence == "Weak" or change_count < 4:
        if important:
            return (
                f"Limited history: only {change_count} change(s) are available, "
                f"so ownership cannot be assessed confidently. Because this path "
                f"may be important, identify its expected maintainer and ensure "
                f"at least one additional reviewer is familiar with it."
            )
        return (
            f"Limited history: only {change_count} change(s) are available, so "
            f"this is an informational signal rather than a confirmed ownership "
            f"risk. Reassess after more activity is recorded."
        )

    # Strong concentration and only one meaningful contributor.
    if concentration >= 90 and meaningful <= 1:
        if important:
            return (
                f"Potential knowledge bottleneck: one meaningful contributor "
                f"accounts for {concentration:.0f}% of activity in a potentially "
                f"important path. Assign a backup maintainer, require a second "
                f"reviewer on the next change, and document the file's key "
                f"decisions."
            )
        return (
            f"High ownership concentration: one meaningful contributor accounts "
            f"for {concentration:.0f}% of activity. Invite another contributor "
            f"to review the next change and make a small follow-up change to "
            f"build shared familiarity."
        )

    # Strong concentration, but multiple meaningful contributors exist.
    if concentration >= 90:
        return (
            f"Activity is concentrated at {concentration:.0f}%, although "
            f"{meaningful} meaningful contributors appear in the history. "
            f"Rotate reviewers and ensure at least one non-primary contributor "
            f"makes or reviews the next change."
        )

    # Important file with moderate concentration or limited coverage.
    if important and (concentration >= 70 or meaningful <= 1):
        return (
            f"This potentially important path has a moderate ownership-risk "
            f"signal: {concentration:.0f}% concentration and {meaningful} "
            f"meaningful contributor(s). Add a backup reviewer and document "
            f"the parts that would be hardest to change without context."
        )

    # Moderate concentration with limited coverage.
    if concentration >= 70 and meaningful <= 1:
        return (
            f"Only {meaningful} meaningful contributor is represented, with "
            f"{concentration:.0f}% concentration. Ask a second contributor to "
            f"review and make a small follow-up change."
        )

    # Moderate concentration with some coverage.
    if concentration >= 70:
        return (
            f"Ownership is somewhat concentrated at {concentration:.0f}%, with "
            f"{meaningful} meaningful contributors represented. Broaden review "
            f"participation and monitor whether concentration increases."
        )

    # Low concentration but still only one meaningful contributor.
    if meaningful <= 1:
        return (
            f"The overall risk is Low, but only {meaningful} meaningful "
            f"contributor is represented. If this file is changing, consider a "
            f"lightweight handoff or review."
        )

    # Healthy distribution.
    return (
        f"No strong concentration signal is indicated: {meaningful} meaningful "
        f"contributors appear across {total_contributors} total contributor(s). "
        f"Continue normal review practices and reassess if ownership becomes "
        f"more concentrated."
    )

def build_recommendations(rows):
    """Create repository-level recommendations from actual ownership patterns."""
    high_rows = [
        row for row in rows
        if row.get("risk_level") == "High"
    ]
    medium_rows = [
        row for row in rows
        if row.get("risk_level") == "Medium"
    ]
    important_rows = [
        row for row in rows
        if row.get("potentially_important")
    ]

    bottleneck_rows = [
        row for row in rows
        if (row.get("concentration_percentage") or 0) >= 90
        and (row.get("meaningful_contributor_count") or 0) <= 1
    ]

    limited_history_rows = [
        row for row in rows
        if row.get("evidence_strength") == "Weak"
    ]

    low_coverage_important = [
        row for row in important_rows
        if (row.get("meaningful_contributor_count") or 0) <= 1
    ]

    recommendations = []

    if bottleneck_rows:
        recommendations.append({
            "priority": "High",
            "title": "Reduce concentrated ownership in key files",
            "issue": (
                f"{len(bottleneck_rows)} file(s) have at least 90% ownership "
                "concentration and one or fewer meaningful contributors."
            ),
            "basis": (
                "These files show both high historical concentration and "
                "limited meaningful contributor coverage. This is a knowledge "
                "sharing opportunity, not proof that the current contributor "
                "is unavailable."
            ),
            "action": (
                "Prioritize backup ownership, second-reviewer requirements, "
                "and a small paired change in the most important affected files."
            ),
            "count": len(bottleneck_rows),
            "risk": "High",
            "important_only": False,
        })

    if low_coverage_important:
        recommendations.append({
            "priority": "High",
            "title": "Improve coverage in potentially important areas",
            "issue": (
                f"{len(low_coverage_important)} potentially important file(s) "
                "have one or fewer meaningful contributors in the analyzed history."
            ),
            "basis": (
                "The path matches configured important-path keywords, while "
                "meaningful contributors are identified using the configured "
                "activity-share threshold."
            ),
            "action": (
                "Confirm which areas are operationally critical, then invite "
                "additional reviewers or maintainers to build familiarity."
            ),
            "count": len(low_coverage_important),
            "risk": "",
            "important_only": True,
        })

    if high_rows:
        recommendations.append({
            "priority": "High",
            "title": "Review high-risk ownership signals",
            "issue": (
                f"{len(high_rows)} file(s) are classified as high risk based on "
                "the available contribution history."
            ),
            "basis": (
                "High-risk classification combines concentration, evidence "
                "strength, contributor coverage, and potential importance."
            ),
            "action": (
                "Review these files in context and decide whether knowledge "
                "sharing, broader review, or documentation is appropriate."
            ),
            "count": len(high_rows),
            "risk": "High",
            "important_only": False,
        })

    if medium_rows:
        recommendations.append({
            "priority": "Medium",
            "title": "Create more shared-ownership opportunities",
            "issue": (
                f"{len(medium_rows)} file(s) have a medium-risk ownership signal."
            ),
            "basis": (
                "The analyzer classified these files Medium using historical "
                "concentration, evidence strength, contributor coverage, and "
                "importance."
            ),
            "action": (
                "Encourage paired changes and broader review participation in "
                "affected areas."
            ),
            "count": len(medium_rows),
            "risk": "Medium",
            "important_only": False,
        })

    if limited_history_rows:
        recommendations.append({
            "priority": "Informational",
            "title": "Reassess files with limited history",
            "issue": (
                f"{len(limited_history_rows)} file(s) have weak evidence "
                "because few changes are recorded."
            ),
            "basis": (
                "The available history is insufficient for a confident "
                "ownership assessment."
            ),
            "action": (
                "Treat these results as preliminary and revisit them after "
                "more activity is recorded."
            ),
            "count": len(limited_history_rows),
            "risk": "",
            "important_only": False,
        })

    return recommendations

def get_risk_counts(rows):
    categories = ("High", "Medium", "Low", "Informational")
    return {
        risk: sum(row.get("risk_level") == risk for row in rows)
        for risk in categories
    }


def start_analysis(repo):
    """Create a run record, run analysis, and update the record."""
    run_id = create_analysis_run(repo["id"])
    result_path = run_db_path(run_id)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = analyze_repo(repo["path"], result_path)

        rows = [
            dict(row)
            for row in get_file_concentration(db_path=result_path)
        ]
        risk_counts = get_risk_counts(rows)

        complete_analysis_run(
            run_id=run_id,
            result_db_path=str(result_path),
            summary=summary,
            file_count=len(rows),
            risk_counts=risk_counts,
        )

        # Keep the old per-repo database updated for existing exports.
        latest_path = repo_db_path(repo["id"])
        shutil.copy2(result_path, latest_path)

        return run_id, None

    except Exception as error:
        fail_analysis_run(
            run_id,
            f"{type(error).__name__}: {error}",
        )
        app.logger.exception("Analysis run %s failed", run_id)
        return run_id, str(error)


def load_report_rows(run):
    result_path = Path(run["result_db_path"])
    if not result_path.exists():
        abort(404)

    rows = [
        dict(row)
        for row in get_file_concentration(db_path=result_path)
    ]

    for row in rows:
        row["suggestion"] = build_file_suggestion(row)

    return rows


@app.route("/")
def index():
    return render_template("index.html", repos=list_repos())


@app.route("/analyze", methods=["POST"])
def analyze():
    repo_path = request.form.get("repo_path", "").strip()

    if not repo_path:
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Please enter a repository path.",
        )

    path = Path(repo_path)
    if not path.is_dir():
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Repository path does not exist.",
        )

    if not (path / ".git").exists():
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Not a Git repository (no .git folder found).",
        )

    repo = get_or_create_repo(str(path))

    try:
        run_id, error = start_analysis(repo)
    except RuntimeError as error:
        return render_template(
            "index.html",
            repos=list_repos(),
            error=str(error),
        )

    if error:
        return redirect(
            url_for("history", analysis_error=error)
        )

    return redirect(
        url_for(
            "repo_detail",
            repo_id=repo["id"],
            from_="home",
        )
    )


@app.route("/analyze-sample", methods=["POST"])
def analyze_sample():
    sample_repo_path = request.form.get("sample_repo", "").strip()

    if not sample_repo_path:
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Please select a sample repository.",
        )

    path = Path(sample_repo_path)
    if not path.is_dir():
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Selected sample repository path does not exist.",
        )

    if not (path / ".git").exists():
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Selected path is not a Git repository.",
        )

    repo = get_or_create_repo(str(path))

    try:
        run_id, error = start_analysis(repo)
    except RuntimeError as error:
        return render_template(
            "index.html",
            repos=list_repos(),
            error=str(error),
        )

    if error:
        return redirect(
            url_for("history", analysis_error=error)
        )

    return redirect(
        url_for(
            "repo_detail",
            repo_id=repo["id"],
            from_="home",
        )
    )


@app.route("/analyze-sample-known", methods=["POST"])
def analyze_sample_known():
    sample_name = request.form.get("sample_name", "").strip()

    if not sample_name:
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Please select a sample repository.",
        )

    samples = {
        "httpie": {
            "url": "https://github.com/httpie/httpie.git",
            "dir_name": "httpie",
        },
        "arrow": {
            "url": "https://github.com/arrow-py/arrow.git",
            "dir_name": "arrow",
        },
        "rich": {
            "url": "https://github.com/Textualize/rich.git",
            "dir_name": "rich",
        },
    }

    sample = samples.get(sample_name)
    if sample is None:
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Unknown sample repository.",
        )

    samples_dir = DATA_DIR / "samples"
    samples_dir.mkdir(exist_ok=True)
    clone_path = samples_dir / sample["dir_name"]

    if not clone_path.exists():
        subprocess.run(
            ["git", "clone", sample["url"], str(clone_path)],
            check=True,
        )
    else:
        subprocess.run(
            ["git", "-C", str(clone_path), "fetch"],
            check=False,
        )

    if not (clone_path / ".git").exists():
        return render_template(
            "index.html",
            repos=list_repos(),
            error="Sample repository is not a valid Git repository.",
        )

    repo = get_or_create_repo(str(clone_path))

    try:
        run_id, error = start_analysis(repo)
    except RuntimeError as error:
        return render_template(
            "index.html",
            repos=list_repos(),
            error=str(error),
        )

    if error:
        return redirect(
            url_for("history", analysis_error=error)
        )

    return redirect(
        url_for(
            "repo_detail",
            repo_id=repo["id"],
            from_="home",
        )
    )


@app.route("/dashboard")
def dashboard():
    """Forward old dashboard URLs to the repository dashboard."""
    repo_id = request.args.get("repo_id", type=int)
    if not repo_id:
        return redirect(url_for("index"))

    return redirect(
        url_for(
            "repo_detail",
            repo_id=repo_id,
            from_=request.args.get("from_", "history"),
            risk=request.args.get("risk", ""),
            q=request.args.get("q", ""),
            page=request.args.get("page", 1),
        )
    )


@app.route("/repo/<int:repo_id>")
def repo_detail(repo_id):
    repo = get_repo_by_id(repo_id)
    if not repo:
        return "Repository not found", 404

    db_path = repo_db_path(repo_id)
    if not db_path.exists():
        return "Repository analysis not found", 404

    rows = [
        dict(row)
        for row in get_file_concentration(db_path=db_path)
    ]

    for row in rows:
        row["suggestion"] = build_file_suggestion(row)

    risk_categories = ("High", "Medium", "Low", "Informational")
    counts = {
        risk: sum(row.get("risk_level") == risk for row in rows)
        for risk in risk_categories
    }

    risk_filter = request.args.get("risk", "").strip()
    if risk_filter not in risk_categories:
        risk_filter = ""

    raw_search_query = request.args.get("q", "").strip()
    normalized_search_query = raw_search_query.lower()

    per_page = 25
    page = request.args.get("page", default=1, type=int) or 1
    page = max(page, 1)

    recommendations = build_recommendations(rows)

    risk_order = {
        "High": 0,
        "Medium": 1,
        "Low": 2,
        "Informational": 3,
    }
    rows.sort(
        key=lambda row: (
            risk_order.get(row.get("risk_level"), 4),
            -(row.get("concentration_percentage") or 0),
            -(row.get("change_count") or 0),
        )
    )

    filtered_rows = [
        row for row in rows
        if (
            not risk_filter
            or row.get("risk_level") == risk_filter
        )
        and (
            not normalized_search_query
            or normalized_search_query
            in (row.get("file_path") or "").lower()
        )
    ]

    total_matching = len(filtered_rows)
    page_count = max(
        (total_matching + per_page - 1) // per_page,
        1,
    )
    page = min(page, page_count)

    start = (page - 1) * per_page
    displayed_rows = filtered_rows[start:start + per_page]

    return render_template(
        "dashboard.html",
        repo=repo,
        concentration=displayed_rows,
        total_files=len(rows),
        high_risk=counts["High"],
        medium_risk=counts["Medium"],
        low_risk=counts["Low"],
        informational=counts["Informational"],
        recommendations=recommendations,
        current_risk_filter=risk_filter,
        search_query=raw_search_query,
        page=page,
        page_count=page_count,
        total_matching=total_matching,
        from_=request.args.get("from_", "history"),
    )

@app.route("/repo/<int:repo_id>/file/<path:file_path>")
def repo_file_detail(repo_id, file_path):
    repo = get_repo_by_id(repo_id)
    if not repo:
        return "Repository not found", 404

    db_path = repo_db_path(repo_id)
    if not db_path.exists():
        abort(404)

    rows = [
        dict(row)
        for row in get_file_concentration(db_path=db_path)
    ]

    file_row = next(
        (row for row in rows if row.get("file_path") == file_path),
        None,
    )
    if file_row is None:
        abort(404)

    file_row["suggestion"] = build_file_suggestion(file_row)

    return render_template(
        "file_detail.html",
        repo=repo,
        row=file_row,
        from_=request.args.get("from_", "history"),
        risk=request.args.get("risk", ""),
        q=request.args.get("q", ""),
        page=request.args.get("page", "1"),
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
    return render_template(
        "history.html",
        repos=list_repos_with_latest_run(),
        analysis_error=request.args.get("analysis_error"),
    )


if __name__ == "__main__":
    app.run(debug=True)