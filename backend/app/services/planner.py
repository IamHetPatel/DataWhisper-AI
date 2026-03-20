import re
from typing import Any

from app.config import get_settings
from app.schemas import (
    AnalyticalEngine,
    AnalyticalOperation,
    DataResolution,
    MetricSpec,
    PlannerFilter,
    QueryIntent,
    QueryPlannerSchema,
    UIRenderingContract,
)
from app.services.llm_gateway import get_gateway
from app.services.semantic_layer import resolve_user_term, get_canonical_channel, get_canonical_channel_for_uuid


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip()


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _infer_intent(q: str) -> QueryIntent:
    if _matches_any(q, [r"\bcompare\b", r"\bvs\.?\b", r"\bdifference\b", r"\bversus\b", r"\bcomparison\b"]):
        return QueryIntent.comparison
    if _matches_any(q, [
        r"\btrend\b", r"\bdrift\b", r"\bover time\b",
        r"\bincrease\w*\b", r"\bdecrease\w*\b",
        r"\bdegradation\b", r"\bdegrad\w*\b", r"\bworsening\b",
        r"\bimproving\b", r"\bchanging over\b",
    ]):
        return QueryIntent.trend_drift
    if _matches_any(q, [
        r"\bcomplian\w*\b", r"\bwithin limits\b", r"\biso\s*\d+\b", r"\bconform\w*\b",
        r"\bwithin spec\b", r"\bplausib\w*\b", r"\bstandard\b", r"\bguideline\w*\b",
        r"\binternal limit\w*\b", r"\bacceptable range\b",
    ]):
        return QueryIntent.validation_compliance
    if _matches_any(q, [
        r"\bhypothesis\b", r"\binfluence\b", r"\beffect of\b", r"\bimpact of\b",
        r"\bif i change\b", r"\bhow does.*affect\b", r"\bcorrelat\w*\b", r"\brelationship\b",
        r"\bparameter.*propert\b", r"\bpropert.*parameter\b",
    ]):
        return QueryIntent.hypothesis
    if _matches_any(q, [r"\banomal\w*\b", r"\boutlier\w*\b", r"\babnormal\b", r"\bsuspicious\b"]):
        return QueryIntent.anomaly_check
    if _matches_any(q, [r"\bsummar\w*\b", r"\boverview\b", r"\bhigh.?level\b"]):
        return QueryIntent.summary
    return QueryIntent.lookup


_COUNT_PATTERNS = [r"\bhow many\b", r"\bcount\b", r"\btotal number\b", r"\bcount of\b", r"\bhow much\b"]


def _intent_to_operation(intent: QueryIntent) -> AnalyticalOperation:
    return {
        QueryIntent.comparison: AnalyticalOperation.welch_t_test,
        QueryIntent.trend_drift: AnalyticalOperation.linear_regression,
        QueryIntent.validation_compliance: AnalyticalOperation.standard_deviation,
        QueryIntent.hypothesis: AnalyticalOperation.welch_t_test,
        QueryIntent.anomaly_check: AnalyticalOperation.iqr_outlier,
        QueryIntent.summary: AnalyticalOperation.standard_deviation,
        QueryIntent.lookup: AnalyticalOperation.raw_fetch,
        QueryIntent.clarification_needed: AnalyticalOperation.raw_fetch,
    }.get(intent, AnalyticalOperation.raw_fetch)


def _intent_to_presentation(intent: QueryIntent) -> str:
    return {
        QueryIntent.comparison: "box_plot",
        QueryIntent.trend_drift: "line_chart",
        QueryIntent.validation_compliance: "compliance_badge",
        QueryIntent.hypothesis: "scatter_plot",
        QueryIntent.anomaly_check: "scatter_plot",
        QueryIntent.summary: "data_table",
        QueryIntent.lookup: "data_table",
        QueryIntent.clarification_needed: "text_only",
    }.get(intent, "data_table")


def _extract_filters(q: str) -> list[PlannerFilter]:
    filters: list[PlannerFilter] = []

    # Customers: Company_N
    companies = list(dict.fromkeys(re.findall(r"\bCompany_\d+\b", q, re.I)))
    if len(companies) > 1:
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.CUSTOMER",
            operator="in",
            value=companies,
        ))
    elif len(companies) == 1:
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.CUSTOMER",
            operator="eq",
            value=companies[0],
        ))

    # Testers: Tester_N or Tester_<word>
    testers = list(dict.fromkeys(re.findall(r"\bTester_\w+\b", q, re.I)))
    if len(testers) > 1:
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.TESTER",
            operator="in",
            value=testers,
        ))
    elif len(testers) == 1:
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.TESTER",
            operator="eq",
            value=testers[0],
        ))

    # Test type
    if re.search(r"\btensile\b", q, re.I):
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.TYPE_OF_TESTING_STR",
            operator="eq",
            value="tensile",
        ))
    elif re.search(r"\bcompression\b", q, re.I):
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.TYPE_OF_TESTING_STR",
            operator="eq",
            value="compression",
        ))
    elif re.search(r"\bflexure\b", q, re.I):
        filters.append(PlannerFilter(
            field_path="TestParametersFlat.TYPE_OF_TESTING_STR",
            operator="eq",
            value="flexure",
        ))

    return filters


# Maps user keywords to canonical search terms for the semantic layer
_METRIC_KEYWORD_MAP: dict[str, list[str]] = {
    "maximum force": ["maximum force"],
    "max force": ["maximum force"],
    "tensile strength": ["maximum force", "upper yield point"],
    "tensile": ["maximum force", "upper yield point"],
    "yield strength": ["upper yield point"],
    "elongation": ["strain at break"],
    "elongation at break": ["strain at break"],
    "stiffness": ["young s modulus"],
    "elastic modulus": ["young s modulus"],
    "young s modulus": ["young s modulus"],
    "strain": ["strain at break"],
    "stress": ["maximum force"],
    "force": ["maximum force"],
}


def _extract_metrics(q: str) -> list[MetricSpec]:
    q_lower = q.lower()
    metrics: list[MetricSpec] = []
    seen_uuids: set[str] = set()

    for keyword, term_list in _METRIC_KEYWORD_MAP.items():
        if keyword in q_lower:
            for term in term_list:
                for candidate in resolve_user_term(term, limit=3):
                    uuid = candidate.get("uuid")
                    if uuid and uuid not in seen_uuids:
                        seen_uuids.add(uuid)
                        unit_table_ids = candidate.get("unit_table_ids", [])
                        metrics.append(MetricSpec(
                            human_label=candidate.get("name", term),
                            resolved_uuid=uuid,
                            source_collection="values",
                            canonical_channel=get_canonical_channel(unit_table_ids),
                        ))
            break  # Only match the first keyword hit

    return metrics[:3]


def _infer_grouping_dimension(q: str, intent: QueryIntent) -> str | None:
    if intent not in {QueryIntent.comparison, QueryIntent.summary, QueryIntent.hypothesis,
                      QueryIntent.validation_compliance}:
        return None
    q_lower = q.lower()
    if re.search(r"\bcustomer\b|\bcompan\w*\b", q_lower):
        return "TestParametersFlat.CUSTOMER"
    if re.search(r"\bmachine\b", q_lower):
        return "TestParametersFlat.MACHINE_TYPE_STR"
    if re.search(r"\bmaterial\b", q_lower):
        return "TestParametersFlat.MATERIAL"
    if re.search(r"\btester\b|\boperator\b", q_lower):
        return "TestParametersFlat.TESTER"
    # Default grouping for comparison intents
    if intent == QueryIntent.comparison:
        return "TestParametersFlat.CUSTOMER"
    return None


def _build_plan_heuristic(question: str, context: dict[str, Any] | None = None) -> QueryPlannerSchema:
    """Regex-based fallback planner that produces a QueryPlannerSchema."""
    q = _normalize_question(question)
    q_lower = q.lower()

    intent = _infer_intent(q_lower)
    operation = _intent_to_operation(intent)

    # Override to count when question asks for a quantity
    is_count = intent == QueryIntent.lookup and _matches_any(q_lower, _COUNT_PATTERNS)
    if is_count:
        operation = AnalyticalOperation.count

    presentation = _intent_to_presentation(intent)
    grouping = _infer_grouping_dimension(q_lower, intent)
    filters = _extract_filters(q)

    # Count queries always target _tests — metrics are irrelevant and would
    # incorrectly route the query to the values collection.
    if is_count:
        metrics: list = []
        target_collections: list = ["tests"]
    else:
        metrics = _extract_metrics(q)
        needs_values = bool(metrics) or intent in {QueryIntent.trend_drift, QueryIntent.anomaly_check}
        target_collections = ["values", "tests"] if needs_values else ["tests"]

    time_interval: str | None = None
    x_axis: str | None = None
    y_axis: str | None = None

    if intent == QueryIntent.trend_drift:
        time_interval = "day"
        x_axis = "date"        # flattenRow extracts _id.date → "date"
        y_axis = "avg_value"   # computed by linear_regression pipeline
    elif intent in {QueryIntent.comparison, QueryIntent.hypothesis}:
        x_axis = "_id"         # MongoDB $group always outputs _id
        y_axis = "mean"        # computed by welch_t_test / std_dev pipeline
    elif intent == QueryIntent.anomaly_check:
        x_axis = "_id"
        y_axis = "mean"

    return QueryPlannerSchema(
        query_intent=intent,
        data_resolution=DataResolution(
            target_collections=target_collections,
            filters=filters,
            metrics=metrics,
        ),
        analytical_engine=AnalyticalEngine(
            operation=operation,
            grouping_dimension=grouping,
            time_series_interval=time_interval,
        ),
        ui_rendering_contract=UIRenderingContract(
            presentation_type=presentation,
            x_axis_mapping=x_axis,
            y_axis_mapping=y_axis,
            summary_text_directive=f"Analyze the {intent.value} of the data for: {question}",
        ),
    )


def _validate_and_normalize_plan(raw: dict[str, Any], question: str) -> QueryPlannerSchema | None:
    """Coerce the raw LLM JSON dict into a validated QueryPlannerSchema."""
    try:
        # query_intent
        valid_intents = {e.value for e in QueryIntent}
        intent_raw = raw.get("query_intent", "summary")
        if intent_raw not in valid_intents:
            intent_raw = "summary"

        # data_resolution
        dr = raw.get("data_resolution") or {}
        raw_collections = dr.get("target_collections", ["tests"])
        normalized_collections: list[str] = []
        for c in (raw_collections if isinstance(raw_collections, list) else ["tests"]):
            c_low = str(c).lower()
            if c_low in {"tests", "_tests", "test"} and "tests" not in normalized_collections:
                normalized_collections.append("tests")
            elif c_low in {"values", "valuecolumns_migrated", "value"} and "values" not in normalized_collections:
                normalized_collections.append("values")
        if not normalized_collections:
            normalized_collections = ["tests"]

        valid_ops = {"eq", "in", "gte", "lte", "regex"}
        filters: list[PlannerFilter] = []
        for f in (dr.get("filters") or []):
            if not isinstance(f, dict):
                continue
            fp = f.get("field_path") or f.get("field")
            op = f.get("operator", "eq")
            val = f.get("value")
            if fp and op in valid_ops:
                filters.append(PlannerFilter(field_path=str(fp), operator=op, value=val))

        metrics: list[MetricSpec] = []
        for m in (dr.get("metrics") or []):
            if not isinstance(m, dict):
                continue
            label = m.get("human_label", "")
            uuid = m.get("resolved_uuid", "")
            src = m.get("source_collection", "values")
            if label and uuid:
                metrics.append(MetricSpec(
                    human_label=str(label),
                    resolved_uuid=str(uuid),
                    source_collection="values" if src not in {"tests", "values"} else src,
                    canonical_channel=get_canonical_channel_for_uuid(str(uuid)),
                ))

        # analytical_engine
        ae = raw.get("analytical_engine") or {}
        valid_ops_ae = {e.value for e in AnalyticalOperation}
        op_raw = ae.get("operation", "lookup")
        if op_raw not in valid_ops_ae:
            op_raw = "raw_fetch"
        grouping = ae.get("grouping_dimension")
        if not isinstance(grouping, str):
            grouping = None
        time_interval = ae.get("time_series_interval")
        if time_interval not in {"day", "week", "month"}:
            time_interval = None

        # ui_rendering_contract
        urc = raw.get("ui_rendering_contract") or {}
        valid_pres = {"data_table", "box_plot", "line_chart", "scatter_plot", "compliance_badge", "text_only"}
        pres = urc.get("presentation_type", "data_table")
        if pres not in valid_pres:
            pres = "data_table"
        x_axis = urc.get("x_axis_mapping")
        y_axis = urc.get("y_axis_mapping")
        directive = urc.get("summary_text_directive") or f"Analyze the data for: {question}"

        return QueryPlannerSchema(
            query_intent=QueryIntent(intent_raw),
            data_resolution=DataResolution(
                target_collections=normalized_collections,
                filters=filters,
                metrics=metrics,
            ),
            analytical_engine=AnalyticalEngine(
                operation=AnalyticalOperation(op_raw),
                grouping_dimension=grouping,
                time_series_interval=time_interval,
            ),
            ui_rendering_contract=UIRenderingContract(
                presentation_type=pres,
                x_axis_mapping=x_axis if isinstance(x_axis, str) else None,
                y_axis_mapping=y_axis if isinstance(y_axis, str) else None,
                summary_text_directive=str(directive),
            ),
        )
    except Exception:  # noqa: BLE001
        return None


def _build_plan_llm(question: str, history: list[dict[str, str]] | None = None) -> QueryPlannerSchema | None:
    """Call LLM with tool use to produce QueryPlannerSchema."""
    gateway = get_gateway()
    if not gateway.is_ready():
        return None

    raw = gateway.generate_query_plan(question, model=gateway.get_model("planner"), history=history)
    if not raw:
        return None

    return _validate_and_normalize_plan(raw, question)


def build_query_plan(question: str, context: dict[str, Any] | None = None, history: list[dict[str, str]] | None = None) -> QueryPlannerSchema:
    """Build a QueryPlannerSchema from a natural language question.

    Tries OpenAI (with resolve_schema_terms tool use) first,
    then falls back to the heuristic regex planner.
    """
    settings = get_settings()
    if settings.planner_mode.lower() == "llm":
        llm_plan = _build_plan_llm(question, history=history)
        if llm_plan is not None:
            return llm_plan

    return _build_plan_heuristic(question, context)


def build_plan(question: str, context: Any = None, history: list[dict[str, str]] | None = None) -> tuple[QueryPlannerSchema, list]:
    """Alias used by main.py — returns (plan, semantic_candidates)."""
    plan = build_query_plan(question, context if isinstance(context, dict) else None, history=history)
    return plan, []
