import json
import math
import re
from typing import Any

import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import get_settings
from .schemas import (
    AnalyticalOperation,
    InsightRequest,
    InsightResponse,
    PlannerRequest,
    PlannerResponse,
    QueryIntent,
    QueryPlannerSchema,
    QueryRunRequest,
    QueryRunResponse,
    SavedQueryResponse,
)

# Person 2's Global Dependencies
from .services.semantic_mapper import SemanticMapper
from .services.stats_engine import StatsEngine
from .services.db_client import DatabaseClient
from .services.query_store import save_query, list_templates

# Person 3's LLM Handlers
from .services.insight import build_insight
from .services.mongo_executor import MongoExecutor
from .services.planner import build_plan

settings = get_settings()
app = FastAPI(title="ZwickRoell Data Whisperer API - Full Integration")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _safe_floats(values: list[Any]) -> list[float]:
    """Filter to finite floats only."""
    return [v for v in values if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v)]


def _compute_stats(plan: QueryPlannerSchema, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run StatsEngine methods appropriate for the query operation."""
    op = plan.analytical_engine.operation
    result: dict[str, Any] = {}

    if op == AnalyticalOperation.linear_regression:
        # Time-series drift: extract avg_value per bucket, ordered by date
        series = _safe_floats([r.get("avg_value") for r in rows])
        if len(series) >= 2:
            result["drift"] = stats.calculate_drift(series)

    elif op in {AnalyticalOperation.welch_t_test, AnalyticalOperation.standard_deviation,
                AnalyticalOperation.iqr_outlier}:
        # Group-level stats: run anomaly detection across group means
        means = _safe_floats([r.get("mean") or r.get("doc_avg") for r in rows])
        if means:
            result["anomalies"] = stats.find_anomalies(means)

        # Welch t-test between exactly 2 groups using their mean/stdDev
        if op == AnalyticalOperation.welch_t_test and len(rows) == 2:
            g1 = _safe_floats([rows[0].get("mean")])
            g2 = _safe_floats([rows[1].get("mean")])
            if g1 and g2:
                result["group_comparison"] = {
                    "group_1": str(rows[0].get("_id", "A")),
                    "group_2": str(rows[1].get("_id", "B")),
                    "mean_1": round(g1[0], 4),
                    "mean_2": round(g2[0], 4),
                    "difference": round(g1[0] - g2[0], 4),
                    "pct_difference": round(abs(g1[0] - g2[0]) / max(g1[0], g2[0]) * 100, 2) if max(g1[0], g2[0]) else 0,
                }

    return result


def _extract_chart_data(
    plan: QueryPlannerSchema, rows: list[dict[str, Any]]
) -> tuple[list[Any], list[Any]]:
    """Return (x_values, y_values) arrays ready for frontend charting."""
    op = plan.analytical_engine.operation
    pres = plan.ui_rendering_contract.presentation_type

    if op == AnalyticalOperation.linear_regression:
        # Line chart: x=dates, y=avg_value
        x = [r.get("_id", {}).get("date", "") if isinstance(r.get("_id"), dict) else str(r.get("_id", "")) for r in rows]
        y = _safe_floats([r.get("avg_value") for r in rows])
        return x, y

    if pres in {"box_plot", "data_table"} and rows and "_id" in rows[0]:
        # Bar/group chart: x=group labels, y=mean values
        x = [str(r.get("_id", "")) for r in rows]
        y = _safe_floats([r.get("mean") for r in rows])
        return x, y

    if pres == "scatter_plot":
        x = list(range(len(rows)))
        y = _safe_floats([r.get("mean") or r.get("doc_avg") or r.get("avg_value") for r in rows])
        return x, y

    return [], []


def _apply_anomaly_alerts(insight: InsightResponse, stats_output: dict[str, Any]) -> None:
    """Prepend proactive anomaly/drift alerts to insight.anomaly_notes in-place."""
    alerts: list[str] = []

    drift = stats_output.get("drift", {})
    if drift.get("is_significant") and drift.get("trend", "flat") != "flat":
        alerts.append(
            f"I noticed something unusual: a statistically significant {drift['trend']} trend "
            f"(slope={drift['slope']}, p={drift['p_value']})."
        )

    anomalies = stats_output.get("anomalies", [])
    if anomalies:
        alerts.append(
            f"I noticed something unusual: {len(anomalies)} group(s) deviate significantly "
            f"from the norm (z-score > 2.0)."
        )
        for a in anomalies[:3]:
            alerts.append(f"  • Index {a['index']}: value={a['value']:.4g}, z-score={a['z_score']}")

    if alerts:
        insight.anomaly_notes = alerts + insight.anomaly_notes


# --- Global Instances ---
mapper = SemanticMapper()
stats = StatsEngine()
db = DatabaseClient()
executor = MongoExecutor()


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "planner_mode": settings.planner_mode,
        "query_mode": settings.query_mode,
        "insight_mode": settings.insight_mode,
        "llm_provider": settings.llm_provider,
        "openai_ready": "yes" if bool(settings.openai_api_key) else "no",
        "mapped_terms_count": str(len(mapper.get_all_mappings()))
    }


@app.post("/planner/plan", response_model=PlannerResponse)
def planner_plan(payload: PlannerRequest) -> PlannerResponse:
    plan, semantic_candidates = build_plan(payload.question, payload.context)
    return PlannerResponse(plan=plan, semantic_candidates=semantic_candidates)


@app.post("/query/run", response_model=QueryRunResponse)
def query_run(payload: QueryRunRequest) -> QueryRunResponse:
    return executor.run_plan(payload.plan, payload.max_repairs)


@app.post("/insight/generate", response_model=InsightResponse)
def insight_generate(payload: InsightRequest) -> InsightResponse:
    # Here Person 3 can wire up Person 2's stats_engine using the data!
    return build_insight(payload.plan, payload.rows, payload.stats)


@app.post("/query", response_model=InsightResponse)
def process_query(req: PlannerRequest) -> InsightResponse:
    """Master orchestration endpoint. Chains Plan -> Run -> Insight."""
    history = [{"role": t.role, "content": t.content} for t in req.conversation_history]
    plan, candidates = build_plan(req.question, req.context, history=history or None)

    if plan is None:
        return InsightResponse(
            summary_3_sentences=[
                "The LLM Orchestration is not yet fully wired.",
                "Your request reached the backend and semantic mapping was initialized.",
                "Person 3 needs to complete the MongoExecutor and LangChain graph files."
            ],
            anomaly_notes=[],
            recommendation="Connect the OpenAI/Anthropic APIs in `services/planner.py`.",
            follow_up_questions=["Test maximum force trend?", "Verify backend logs?"],
            chart_config={},
            audit_log=["Received query: " + req.question, "Planner returned None (Mock Mode)"]
        )

    run_resp = executor.run_plan_with_repair(plan, settings.max_query_repairs, semantic_candidates=candidates)

    if run_resp is None:
        return InsightResponse(
            summary_3_sentences=["Plan was created, but execution failed."],
            anomaly_notes=[],
            recommendation="Review the generated Mongo Query.",
            follow_up_questions=[],
            chart_config={},
            audit_log=["Plan created but execution failed."]
        )

    stats_output = _compute_stats(plan, run_resp.rows)
    final_insight = build_insight(plan, run_resp.rows, stats_output)
    final_insight.x_values, final_insight.y_values = _extract_chart_data(plan, run_resp.rows)
    final_insight.stats_summary = stats_output
    _apply_anomaly_alerts(final_insight, stats_output)

    # Auto-save successful queries as reusable templates
    if run_resp.row_count > 0:
        save_query(
            question=req.question,
            intent=plan.query_intent.value,
            row_count=run_resp.row_count,
            x_values=final_insight.x_values,
            y_values=final_insight.y_values,
            plan_dict=plan.model_dump(),
        )

    return final_insight


@app.get("/query/stream")
def query_stream(question: str = Query(..., min_length=3)):
    """SSE streaming endpoint — yields planning/querying/insight stages progressively."""
    def _generate():
        def _event(data: dict) -> str:
            return f"data: {json.dumps(data, default=str)}\n\n"

        yield _event({"stage": "planning", "status": "started"})
        try:
            plan, candidates = build_plan(question)
            yield _event({"stage": "planning", "status": "done",
                          "intent": plan.query_intent.value,
                          "operation": plan.analytical_engine.operation.value})
        except Exception as exc:  # noqa: BLE001
            yield _event({"stage": "planning", "status": "error", "message": str(exc)})
            return

        yield _event({"stage": "querying", "status": "started"})
        try:
            run_resp = executor.run_plan_with_repair(plan, settings.max_query_repairs)
            yield _event({"stage": "querying", "status": "done", "row_count": run_resp.row_count})
        except Exception as exc:  # noqa: BLE001
            yield _event({"stage": "querying", "status": "error", "message": str(exc)})
            return

        yield _event({"stage": "insight", "status": "started"})
        stats_output = _compute_stats(plan, run_resp.rows)
        insight = build_insight(plan, run_resp.rows, stats_output)
        insight.x_values, insight.y_values = _extract_chart_data(plan, run_resp.rows)
        insight.stats_summary = stats_output
        _apply_anomaly_alerts(insight, stats_output)
        yield _event({"stage": "done", "result": insight.model_dump()})

    return StreamingResponse(_generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/queries/templates", response_model=list[SavedQueryResponse])
def get_templates():
    """Return the most recent saved queries for reuse."""
    return list_templates(limit=20)


@app.delete("/queries/templates")
def clear_templates():
    """Clear all saved templates (useful during demo/testing)."""
    from pymongo import MongoClient
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
        with client:
            db = client[settings.mongo_db_name] if settings.mongo_db_name else client.get_default_database()
            result = db["saved_queries"].delete_many({})
            return {"deleted": result.deleted_count}
    except Exception as exc:  # noqa: BLE001
        return {"deleted": 0, "error": str(exc)}
