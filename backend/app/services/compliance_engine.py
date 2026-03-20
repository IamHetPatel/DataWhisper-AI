"""
ISO compliance and plausibility checking for materials testing data.
Used when query intent is validation_compliance.
"""
import re
from typing import Any

# ---------------------------------------------------------------------------
# ISO standard limits for common tensile / materials test metrics.
# Tuple: (min_acceptable, max_acceptable)
# Force in N, strain in %, modulus in MPa.
# ---------------------------------------------------------------------------
_ISO_LIMITS: dict[str, dict[str, tuple[float, float]]] = {
    # ISO 527 – Plastics: determination of tensile properties
    "iso 527": {
        "maximum force":             (0.5,   500_000),
        "tensile strength":          (5,     200),
        "strain at break":           (0.1,   1_000),
        "strain at maximum force":   (0.1,   800),
        "nominal strain at maximum force": (0.1, 800),
        "young s modulus":           (10,    10_000),
        "upper yield point":         (5,     200),
    },
    # ISO 6892 – Metallic materials: tensile testing
    "iso 6892": {
        "maximum force":             (100,   2_000_000),
        "tensile strength":          (100,   2_500),
        "strain at break":           (0.5,   60),
        "upper yield point":         (50,    2_000),
        "young s modulus":           (50_000, 300_000),
    },
    # ISO 178 – Plastics: flexural properties
    "iso 178": {
        "maximum force":             (0.1,   50_000),
        "flexural strength":         (10,    500),
        "flexural modulus":          (100,   20_000),
    },
    # ISO 868 / ASTM D2240 – Shore hardness (dimensionless 0-100)
    "iso 868": {
        "shore hardness":            (0,     100),
    },
    # Generic / fallback – very wide plausibility bounds
    "generic": {
        "maximum force":             (0.001, 5_000_000),
        "strain at break":           (0,     2_000),
        "young s modulus":           (0.01,  600_000),
        "upper yield point":         (0,     3_000),
    },
}


def _parse_standard(text: str) -> str | None:
    """Extract the first ISO standard name from free text, e.g. 'ISO 527-1:2019' → 'iso 527'."""
    m = re.search(r"\biso\s*(\d+)", text, re.I)
    if m:
        return f"iso {m.group(1)}"
    return None


def _get_limits(standard_key: str | None, metric_label: str) -> tuple[float, float] | None:
    """Return (lo, hi) limits for a metric under the resolved standard key."""
    key = standard_key or "generic"
    limits_dict = _ISO_LIMITS.get(key, _ISO_LIMITS["generic"])
    metric_norm = metric_label.lower().strip()

    # Exact match
    if metric_norm in limits_dict:
        return limits_dict[metric_norm]
    # Partial match (substring)
    for lk, lv in limits_dict.items():
        if lk in metric_norm or metric_norm in lk:
            return lv
    # Fall back to generic dict
    if key != "generic":
        for lk, lv in _ISO_LIMITS["generic"].items():
            if lk in metric_norm or metric_norm in lk:
                return lv
    return None


def check_compliance(
    rows: list[dict[str, Any]],
    metric_labels: list[str],
    directive_text: str = "",
) -> dict[str, Any]:
    """
    Compare group-level means against ISO plausibility / compliance limits.

    Parameters
    ----------
    rows            : Query result rows with keys ``_id``, ``mean``, ``stdDev``, ``count``.
    metric_labels   : Human-readable metric names (from plan.data_resolution.metrics).
    directive_text  : The planner's summary directive — used to extract ISO standard reference.

    Returns
    -------
    dict with keys:
        standard_applied, overall_pass, summary, groups (list of per-group dicts)
    """
    raw_standard = _parse_standard(directive_text)
    standard_key = raw_standard  # e.g. "iso 527" or None → fallback to "generic"

    result: dict[str, Any] = {
        "standard_applied": raw_standard.upper().replace("ISO ", "ISO ") if raw_standard else "generic plausibility",
        "overall_pass": True,
        "groups": [],
    }

    for row in rows:
        group_id = str(row.get("_id", "unknown"))
        mean_val = row.get("mean")
        std_val = float(row.get("stdDev") or 0.0)
        count = row.get("count", 0)

        group_entry: dict[str, Any] = {
            "group": group_id,
            "mean": round(float(mean_val), 4) if mean_val is not None else None,
            "std_dev": round(std_val, 4),
            "count": count,
            "status": "pass",
            "violations": [],
        }

        if mean_val is not None:
            for metric in metric_labels:
                limits = _get_limits(standard_key, metric)
                if limits:
                    lo, hi = limits
                    val = float(mean_val)
                    if not (lo <= val <= hi):
                        group_entry["status"] = "fail"
                        group_entry["violations"].append(
                            f"{metric}: mean={val:.4g} outside [{lo:g}, {hi:g}]"
                        )

        if group_entry["status"] == "fail":
            result["overall_pass"] = False

        result["groups"].append(group_entry)

    pass_count = sum(1 for g in result["groups"] if g["status"] == "pass")
    total = len(result["groups"])
    std_label = result["standard_applied"]
    result["summary"] = (
        f"{pass_count}/{total} groups pass {std_label} limits."
        if total
        else f"No groups to evaluate against {std_label}."
    )
    return result
