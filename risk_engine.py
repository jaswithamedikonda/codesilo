from config import (
    HIGH_CONCENTRATION_THRESHOLD,
    MEDIUM_CONCENTRATION_THRESHOLD,
    STRONG_EVIDENCE_MIN_CHANGES,
    MODERATE_EVIDENCE_MIN_CHANGES,
)


def classify_risk(
    concentration_percentage,
    evidence_strength,
    meaningful_contributor_count,
    potentially_important,
):
    # Weak evidence: treat as informational unless important
    if evidence_strength == "Weak":
        if potentially_important:
            return "Medium"
        else:
            return "Informational"

    # Very few meaningful contributors: low-confidence signal
    if meaningful_contributor_count <= 1:
        if potentially_important:
            return "Medium"
        else:
            # Still a silo, but low confidence due to limited history
            return "Low"

    # Strong evidence
    if evidence_strength == "Strong":
        if concentration_percentage >= HIGH_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "High"
            else:
                return "Medium"

        if concentration_percentage >= MEDIUM_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "Medium"
            else:
                return "Low"

        return "Low"

    # Moderate evidence
    if evidence_strength == "Moderate":
        if concentration_percentage >= HIGH_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "High"
            else:
                return "Medium"

        if concentration_percentage >= MEDIUM_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "Medium"
            else:
                return "Low"

        return "Low"

    # Fallback
    return "Informational"