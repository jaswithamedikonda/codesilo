from collections import Counter
from pathlib import PurePosixPath


def parent_directory(file_path: str) -> str:
    # Works for both Unix and Windows paths in practice
    p = PurePosixPath(file_path.replace("\\", "/"))
    if len(p.parts) > 1:
        return p.parts[-2]
    return "(root)"


def generate_repo_suggestions(concentration_rows):
    suggestions = []

    high_risk_files = [
        row for row in concentration_rows
        if row.get("risk_level") == "High"
    ]
    medium_risk_files = [
        row for row in concentration_rows
        if row.get("risk_level") == "Medium"
    ]
    low_risk_files = [
        row for row in concentration_rows
        if row.get("risk_level") == "Low"
    ]
    informational_files = [
        row for row in concentration_rows
        if row.get("risk_level") == "Informational"
    ]

    high_risk_count = len(high_risk_files)
    medium_risk_count = len(medium_risk_files)
    total_files = len(concentration_rows)

    if high_risk_count > 0:
        high_dirs = Counter(
            parent_directory(row["file_path"])
            for row in high_risk_files
        )
        top_high_dirs = [
            directory for directory, _ in high_dirs.most_common(3)
        ]

        concentration_values = [
            row["concentration_percentage"]
            for row in high_risk_files
            if row.get("concentration_percentage") is not None
        ]
        min_concentration = min(concentration_values) if concentration_values else 0
        max_concentration = max(concentration_values) if concentration_values else 0

        meaningful_counts = [
            row["meaningful_contributor_count"]
            for row in high_risk_files
        ]
        average_meaningful = (
            sum(meaningful_counts) / len(meaningful_counts)
            if meaningful_counts
            else 0
        )

        directories = ", ".join(top_high_dirs) if top_high_dirs else "various directories"

        suggestions.append(
            f"{high_risk_count} high-risk file(s) were found, mainly in {directories}. "
            f"Their top-contributor concentration ranges from "
            f"{min_concentration:.0f}% to {max_concentration:.0f}%, with "
            f"{average_meaningful:.1f} meaningful contributors on average. "
            "Priority actions: assign a co-owner for each high-risk file, require dual review "
            "for changes, and document important logic, edge cases, and operational steps."
        )

    if medium_risk_count > 0:
        medium_dirs = Counter(
            parent_directory(row["file_path"])
            for row in medium_risk_files
        )
        top_medium_dirs = [
            directory for directory, _ in medium_dirs.most_common(3)
        ]

        concentration_values = [
            row["concentration_percentage"]
            for row in medium_risk_files
            if row.get("concentration_percentage") is not None
        ]
        min_concentration = min(concentration_values) if concentration_values else 0
        max_concentration = max(concentration_values) if concentration_values else 0

        directories = ", ".join(top_medium_dirs) if top_medium_dirs else "various directories"

        suggestions.append(
            f"{medium_risk_count} medium-risk file(s) were found, mainly in {directories}. "
            f"Their top-contributor concentration ranges from "
            f"{min_concentration:.0f}% to {max_concentration:.0f}%. "
            "Recommended actions: choose 1–2 engineers to shadow current owners, rotate small "
            "changes over time, and verify that tests and documentation explain core behavior."
        )

    high_medium_files = high_risk_files + medium_risk_files

    if len(high_medium_files) >= 2:
        directory_counts = Counter(
            parent_directory(row["file_path"])
            for row in high_medium_files
        )

        for directory, count in directory_counts.most_common(3):
            if count >= 2:
                suggestions.append(
                    f"{directory} contains {count} high- or medium-risk file(s). "
                    "Treat this as a concentrated knowledge area and plan focused pairing, "
                    "documentation, and ownership rotation for the module."
                )
                break

    low_and_info_count = len(low_risk_files) + len(informational_files)

    if (
        total_files > 0
        and low_and_info_count / total_files >= 0.7
        and high_risk_count == 0
    ):
        suggestions.append(
            f"{low_and_info_count} of {total_files} files are low-risk or informational. "
            "Overall, this indicates broadly distributed knowledge. Continue shared code reviews, "
            "documentation, and gradual ownership rotation."
        )

    if not suggestions:
        suggestions.append(
            "No immediate knowledge-silo action is required from the current history. "
            "Continue monitoring contributor concentration as the repository evolves."
        )

    return suggestions

def generate_file_suggestion(row):
    risk_level = row.get("risk_level", "Informational")
    concentration = row.get("concentration_percentage")
    evidence_strength = row.get("evidence_strength", "Weak")
    meaningful_contributors = row.get("meaningful_contributor_count", 0)
    potentially_important = row.get("potentially_important", False)
    top_contributor = row.get("top_contributor", "an unknown contributor")
    file_path = row.get("file_path", "this file")
    directory = parent_directory(file_path)

    if concentration is None:
        concentration_text = "an unknown percentage"
        concentration_number = None
    else:
        concentration_text = f"{concentration:.0f}%"
        concentration_number = concentration

    if risk_level == "High":
        suggestion = (
            f"High silo risk: {concentration_text} of recorded change activity "
            f"is linked to {top_contributor}. This file is in {directory}. "
            "Assign at least one co-owner, require two reviewers for changes, "
            "and document important behavior, edge cases, and operational steps."
        )

        if meaningful_contributors <= 1:
            suggestion += (
                f" Only {meaningful_contributors} meaningful contributor is "
                "recorded, so prioritize pairing and a knowledge-transfer session."
            )

        return suggestion

    if risk_level == "Medium":
        if potentially_important:
            return (
                f"Medium silo risk: {concentration_text} of recorded change "
                f"activity is linked to {top_contributor} in an important file "
                f"within {directory}. Pair on upcoming changes, nominate a "
                "backup owner, and verify that tests and documentation cover "
                "the core behavior."
            )

        return (
            f"Medium silo risk: {concentration_text} of recorded change activity "
            f"is linked to {top_contributor}. Encourage additional contributors "
            "through code review, pairing, and rotation of smaller changes."
        )

    if risk_level == "Low":
        if concentration_number is not None and concentration_number >= 50:
            return (
                f"Low silo risk, although {concentration_text} of recorded "
                f"change activity is linked to {top_contributor}. Continue "
                "code reviews and shared ownership, and involve another "
                "contributor in future changes where practical."
            )

        return (
            f"Low silo risk: change activity is reasonably distributed, with "
            f"{concentration_text} linked to the top contributor and "
            f"{meaningful_contributors} meaningful contributors. No immediate "
            "action is needed; maintain review and documentation practices."
        )

    if risk_level == "Informational":
        if evidence_strength == "Weak":
            return (
                "Informational result: limited change history is available for "
                "this file. No immediate action is recommended; reassess after "
                "more commits provide stronger evidence."
            )

        return (
            "Informational result: the available history does not indicate a "
            "clear knowledge-silo concern. Continue monitoring as the file evolves."
        )

    return "No specific recommendation is available for this file."