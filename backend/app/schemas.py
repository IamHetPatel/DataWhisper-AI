from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# New QueryPlannerSchema models (primary data contract for the revamped API)
# ---------------------------------------------------------------------------

class QueryIntent(str, Enum):
    lookup = "lookup"
    comparison = "comparison"
    trend_drift = "trend_drift"
    anomaly_check = "anomaly_check"
    validation_compliance = "validation_compliance"
    hypothesis = "hypothesis"
    summary = "summary"
    clarification_needed = "clarification_needed"


class PlannerFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_path: str
    operator: Literal["eq", "in", "gte", "lte", "regex"]
    value: Any


class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_label: str
    resolved_uuid: str
    source_collection: Literal["tests", "values"] = "values"


class DataResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_collections: list[Literal["tests", "values"]]
    filters: list[PlannerFilter] = Field(default_factory=list)
    metrics: list[MetricSpec] = Field(default_factory=list)


class AnalyticalOperation(str, Enum):
    raw_fetch = "raw_fetch"
    count = "count"
    welch_t_test = "welch_t_test"
    iqr_outlier = "iqr_outlier"
    linear_regression = "linear_regression"
    standard_deviation = "standard_deviation"


class AnalyticalEngine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: AnalyticalOperation
    grouping_dimension: str | None = None
    time_series_interval: Literal["day", "week", "month"] | None = None


class UIRenderingContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation_type: Literal[
        "data_table", "box_plot", "line_chart", "scatter_plot", "compliance_badge", "text_only"
    ]
    x_axis_mapping: str | None = None
    y_axis_mapping: str | None = None
    summary_text_directive: str


class QueryPlannerSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_intent: QueryIntent
    data_resolution: DataResolution
    analytical_engine: AnalyticalEngine
    ui_rendering_contract: UIRenderingContract


# ---------------------------------------------------------------------------
# Shared collection / query execution models (used by mongo_executor)
# ---------------------------------------------------------------------------

class CollectionName(str, Enum):
    tests = "Tests"
    values = "Values"


class MongoQueryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: CollectionName
    pipeline: list[dict[str, Any]]
    explanation: str
    expected_shape: list[str] = Field(default_factory=list)


class QueryAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int
    pipeline: list[dict[str, Any]]
    error: str | None = None
    corrected_from_previous: bool = False


class QueryRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed"]
    candidate: MongoQueryCandidate
    attempts: list[QueryAttempt]
    row_count: int
    rows: list[dict[str, Any]]
    corrected_automatically: bool


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str  # "user" or "assistant"
    content: str


class PlannerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3)
    context: Any = Field(default_factory=dict)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: QueryPlannerSchema
    semantic_candidates: list[Any] = Field(default_factory=list)


class QueryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: QueryPlannerSchema
    max_repairs: int | None = Field(default=None, ge=0, le=5)
    semantic_candidates: list[Any] = Field(default_factory=list)


class InsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: QueryPlannerSchema
    rows: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class SavedQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    intent: str
    created_at: str
    row_count: int
    x_values: list[Any] = Field(default_factory=list)
    y_values: list[Any] = Field(default_factory=list)


class InsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_3_sentences: list[str]
    anomaly_notes: list[str]
    recommendation: str
    follow_up_questions: list[str]
    chart_config: dict[str, Any]
    x_values: list[Any] = Field(default_factory=list)
    y_values: list[Any] = Field(default_factory=list)
    stats_summary: dict[str, Any] = Field(default_factory=dict)
    audit_log: list[str] = Field(default_factory=list)
