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
    # Weak evidence: not enough history to be confident
    if evidence_strength == "Weak":
        if potentially_important:
            return "Medium"
        return "Informational"

    # Strong evidence
    if evidence_strength == "Strong":
        # Very concentrated ownership
        if concentration_percentage >= HIGH_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "High"
            # Non-important but very concentrated with strong evidence
            if meaningful_contributor_count <= 1:
                return "High"
            return "Medium"

        # Moderate concentration
        if concentration_percentage >= MEDIUM_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "Medium"
            if meaningful_contributor_count <= 1:
                return "Medium"
            return "Low"

        # Lower concentration
        if meaningful_contributor_count <= 1 and potentially_important:
            return "Medium"
        return "Low"

    # Moderate evidence
    if evidence_strength == "Moderate":
        if concentration_percentage >= HIGH_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "High"
            if meaningful_contributor_count <= 1:
                return "Medium"
            return "Medium"

        if concentration_percentage >= MEDIUM_CONCENTRATION_THRESHOLD:
            if potentially_important:
                return "Medium"
            if meaningful_contributor_count <= 1:
                return "Medium"
            return "Low"

        if meaningful_contributor_count <= 1 and potentially_important:
            return "Medium"
        return "Low"

    # Fallback
    return "Informational"