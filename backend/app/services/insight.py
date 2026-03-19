import logging
import math
from typing import Any

from app.config import get_settings
from app.schemas import InsightResponse, QueryIntent, QueryPlannerSchema
from app.services.llm_gateway import get_gateway


def _chart_for_plan(plan: QueryPlannerSchema) -> dict[str, Any]:
    pres = plan.ui_rendering_contract.presentation_type
    x = plan.ui_rendering_contract.x_axis_mapping
    y = plan.ui_rendering_contract.y_axis_mapping

    if pres == "line_chart":
        return {"type": "line", "x": x or "uploadDate", "y": y or "value", "title": "Trend over time"}
    if pres == "box_plot":
        return {"type": "bar", "x": x or "group", "y": y or "value", "title": "Comparison view"}
    if pres == "scatter_plot":
        return {"type": "scatter", "x": x or "index", "y": y or "value", "title": "Data distribution"}
    if pres == "compliance_badge":
        return {"type": "table", "title": "Compliance check"}
    return {"type": "table", "title": "Result overview"}


def _follow_ups_for_intent(intent: QueryIntent) -> list[str]:
    if intent == QueryIntent.comparison:
        return [
            "Show the same comparison for a different time range.",
            "Compare the same metric on another machine.",
            "Run a significance test with stricter confidence level.",
        ]
    if intent == QueryIntent.trend_drift:
        return [
            "Limit the trend to the last 30 days.",
            "Highlight values near boundary violations.",
            "Compare this trend against another customer.",
        ]
    if intent == QueryIntent.validation_compliance:
        return [
            "List only records that violate the limit.",
            "Show compliance by machine.",
            "Generate a compliance summary.",
        ]
    if intent == QueryIntent.anomaly_check:
        return [
            "Show only the top 10 outliers.",
            "Filter anomalies by customer.",
            "Compare anomaly rate across machines.",
        ]
    return [
        "Apply a narrower filter window.",
        "Compare against another customer or machine.",
        "Generate a reusable report from this result.",
    ]


def _sample_rows(rows: list[dict[str, Any]], max_rows: int = 8, max_keys: int = 10) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for row in rows[:max_rows]:
        if not isinstance(row, dict):
            continue
        keys = list(row.keys())[:max_keys]
        sample.append({key: row.get(key) for key in keys})
    return sample


_log = logging.getLogger(__name__)


def _unique_values(rows: list[dict[str, Any]], field: str, limit: int = 5) -> list[str]:
    """Collect unique non-empty string values for a field across rows."""
    seen: list[str] = []
    dedup: set[str] = set()
    for row in rows:
        val = row.get(field)
        if val and isinstance(val, str) and val not in dedup:
            dedup.add(val)
            seen.append(val)
            if len(seen) >= limit:
                break
    return seen


def _build_summary_sentences(
    plan: QueryPlannerSchema,
    rows: list[dict[str, Any]],
) -> list[str]:
    """Return exactly 3 data-driven summary sentences."""
    row_count = len(rows)
    intent = plan.query_intent

    if row_count == 0:
        return [
            "No matching records were found for this query.",
            "Consider broadening the filter criteria or adjusting the date range.",
            "Use the follow-up suggestions below to explore the available data.",
        ]

    # Count result (single row with 'total' key)
    if row_count == 1 and "total" in rows[0]:
        total = rows[0]["total"]
        return [
            f"The database contains {total} test record(s) matching the query.",
            "This count reflects all tests passing the applied filters.",
            "Add filters for customer, material, or date to narrow the result.",
        ]

    if intent == QueryIntent.lookup:
        customers = _unique_values(rows, "customer")
        materials = _unique_values(rows, "material")
        s1 = f"Retrieved {row_count} test record(s) from the database."
        s2 = (
            f"Customer(s) represented: {', '.join(customers)}."
            if customers
            else f"Records span {row_count} tests across the full dataset."
        )
        s3 = (
            f"Material(s) tested: {', '.join(materials)}."
            if materials
            else "Apply a customer or material filter to narrow results."
        )
        return [s1, s2, s3]

    if intent == QueryIntent.comparison:
        groups = [str(r.get("_id", "")) for r in rows if r.get("_id") is not None]
        means = [r.get("mean") for r in rows if isinstance(r.get("mean"), (int, float)) and not math.isnan(r.get("mean")) and not math.isinf(r.get("mean"))]
        s1 = f"Comparison analysis completed across {row_count} group(s)."
        s2 = f"Groups: {', '.join(str(g) for g in groups[:5])}." if groups else "Groups compared based on available data."
        if len(means) >= 2:
            s3 = f"Mean values range from {min(means):.4g} to {max(means):.4g}; review the box plot for spread."
        else:
            s3 = "Review the box plot to compare distributions across groups."
        return [s1, s2, s3]

    if intent == QueryIntent.trend_drift:
        dates = [
            str(r.get("_id", {}).get("date", ""))[:10]
            for r in rows
            if isinstance(r.get("_id"), dict) and r["_id"].get("date")
        ]
        avg_vals = [r.get("avg_value") for r in rows if isinstance(r.get("avg_value"), (int, float)) and not math.isnan(r.get("avg_value")) and not math.isinf(r.get("avg_value"))]
        s1 = f"Trend analysis covers {row_count} time-bucketed data point(s)."
        s2 = (
            f"Date range: {dates[0]} to {dates[-1]}."
            if len(dates) >= 2
            else "Time-series data extracted for trend visualization."
        )
        if len(avg_vals) >= 2:
            direction = "upward" if avg_vals[-1] > avg_vals[0] else "downward"
            s3 = f"Overall {direction} movement detected from {avg_vals[0]:.4g} to {avg_vals[-1]:.4g}."
        else:
            s3 = "Review the line chart to identify any systematic drift or degradation pattern."
        return [s1, s2, s3]

    if intent == QueryIntent.anomaly_check:
        s1 = f"Anomaly detection applied to {row_count} group(s) using the IQR method."
        std_devs = [r.get("stdDev") for r in rows if isinstance(r.get("stdDev"), (int, float))]
        s2 = (
            f"Standard deviation range: {min(std_devs):.4g} to {max(std_devs):.4g}."
            if len(std_devs) >= 2
            else "Inter-quartile range computed for each group."
        )
        s3 = "Review the scatter chart for data points that deviate significantly from the norm."
        return [s1, s2, s3]

    if intent == QueryIntent.validation_compliance:
        s1 = f"Compliance check completed on {row_count} result group(s)."
        s2 = "Standard deviation and mean values have been computed for each group."
        s3 = "Review the compliance badge to identify groups that may violate specified limits."
        return [s1, s2, s3]

    if intent == QueryIntent.summary:
        groups = [str(r.get("_id", "")) for r in rows if r.get("_id") is not None]
        s1 = f"Summary analysis returned {row_count} result group(s)."
        s2 = f"Top groups: {', '.join(str(g) for g in groups[:5])}." if groups else "Data aggregated across all available records."
        s3 = plan.ui_rendering_contract.summary_text_directive
        return [s1, s2, s3]

    # Generic fallback
    return [
        f"Query returned {row_count} result(s) for the {intent.value} analysis.",
        f"Applied {plan.analytical_engine.operation.value} operation to the dataset.",
        plan.ui_rendering_contract.summary_text_directive,
    ]


def _build_insight_mock(
    plan: QueryPlannerSchema,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> InsightResponse:
    row_count = len(rows)
    anomalies = stats.get("anomalies", []) if isinstance(stats, dict) else []

    summary = _build_summary_sentences(plan, rows)

    anomaly_notes: list[str] = []
    if isinstance(anomalies, list) and anomalies:
        anomaly_notes.append(f"Detected {len(anomalies)} potential anomalies in the stats payload.")
    elif plan.query_intent == QueryIntent.anomaly_check:
        anomaly_notes.append("IQR-based outlier scoring applied; review min/max vs mean spread per group.")
    else:
        anomaly_notes.append("No anomaly signal detected in this response.")

    audit_log = [
        f"Intent: {plan.query_intent.value}",
        f"Operation: {plan.analytical_engine.operation.value}",
        f"Row count: {row_count}",
        f"Metrics: {[m.human_label for m in plan.data_resolution.metrics]}",
    ]

    return InsightResponse(
        summary_3_sentences=summary,
        anomaly_notes=anomaly_notes,
        recommendation=(
            "Use the follow-up suggestions to narrow filters, "
            "then save this as a reusable template if the result is useful."
        ),
        follow_up_questions=_follow_ups_for_intent(plan.query_intent),
        chart_config=_chart_for_plan(plan),
        chart_data=rows,
        audit_log=audit_log,
    )


def _build_insight_llm(
    plan: QueryPlannerSchema,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> InsightResponse | None:
    gateway = get_gateway()
    if not gateway.is_ready():
        return None

    row_count = len(rows)
    fallback = _build_insight_mock(plan, rows, stats)

    system_prompt = (
        "You are an AI data analyst for materials testing. "
        "Return strict JSON only and keep statements grounded in the provided data."
    )
    user_prompt = (
        "Generate insight JSON for this query output.\n"
        "Required schema:\n"
        "{\n"
        '  "summary_3_sentences": string[3],\n'
        '  "anomaly_notes": string[],\n'
        '  "recommendation": string,\n'
        '  "follow_up_questions": string[],\n'
        '  "chart_config": {"type": "line|bar|scatter|table", "x": string?, "y": string?, "title": string},\n'
        '  "audit_log": string[]\n'
        "}\n"
        "Rules:\n"
        "- summary_3_sentences must contain exactly 3 concise sentences.\n"
        "- follow_up_questions should contain 3 to 5 actionable items.\n"
        "- If row_count is 0, explicitly state that data is insufficient.\n"
        "- Never include markdown.\n"
        f"Query intent: {plan.query_intent.value}\n"
        f"Operation: {plan.analytical_engine.operation.value}\n"
        f"Directive: {plan.ui_rendering_contract.summary_text_directive}\n"
        f"Metrics: {[m.human_label for m in plan.data_resolution.metrics]}\n"
        f"Row count: {row_count}\n"
        f"Sample rows: {_sample_rows(rows)}\n"
        f"Stats: {stats if isinstance(stats, dict) else {}}\n"
    )

    result = gateway.generate_json(
        model=gateway.get_model("insight"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1400,
        temperature=0.1,
    )
    if not result:
        _log.warning("Insight LLM returned no result for intent=%s", plan.query_intent.value)
        return None

    def _norm_str_list(value: Any, fallback_list: list[str], max_items: int | None = None) -> list[str]:
        if not isinstance(value, list):
            return fallback_list
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if not normalized:
            return fallback_list
        return normalized[:max_items] if max_items else normalized

    summary = _norm_str_list(result.get("summary_3_sentences"), fallback.summary_3_sentences, 3)
    if len(summary) < 3:
        summary = (summary + fallback.summary_3_sentences)[:3]

    anomaly_notes = _norm_str_list(result.get("anomaly_notes"), fallback.anomaly_notes, 5)
    follow_ups = _norm_str_list(result.get("follow_up_questions"), fallback.follow_up_questions, 5)
    if len(follow_ups) < 3:
        follow_ups = (follow_ups + fallback.follow_up_questions)[:3]

    rec_raw = result.get("recommendation")
    recommendation = (
        rec_raw.strip() if isinstance(rec_raw, str) and rec_raw.strip() else fallback.recommendation
    )

    chart_raw = result.get("chart_config")
    if isinstance(chart_raw, dict):
        valid_types = {"line", "bar", "scatter", "table"}
        chart_type = str(chart_raw.get("type", "table")).lower()
        if chart_type not in valid_types:
            chart_type = "table"
        chart_config: dict[str, Any] = {
            "type": chart_type,
            "title": str(chart_raw.get("title") or fallback.chart_config.get("title", "Results")).strip(),
        }
        if chart_type != "table":
            if x_val := chart_raw.get("x"):
                chart_config["x"] = str(x_val)
            if y_val := chart_raw.get("y"):
                chart_config["y"] = str(y_val)
    else:
        chart_config = fallback.chart_config

    audit_log = _norm_str_list(result.get("audit_log"), fallback.audit_log, 8)

    try:
        return InsightResponse(
            summary_3_sentences=summary,
            anomaly_notes=anomaly_notes,
            recommendation=recommendation,
            follow_up_questions=follow_ups,
            chart_config=chart_config,
            chart_data=rows,
            audit_log=audit_log,
        )
    except Exception:  # noqa: BLE001
        return None


def build_insight(
    plan: QueryPlannerSchema,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> InsightResponse:
    settings = get_settings()
    if settings.insight_mode.lower() == "llm":
        llm_insight = _build_insight_llm(plan, rows, stats)
        if llm_insight is not None:
            return llm_insight
        fallback = _build_insight_mock(plan, rows, stats)
        fallback.audit_log.append("Insight LLM unavailable, using mock fallback.")
        return fallback

    return _build_insight_mock(plan, rows, stats)
