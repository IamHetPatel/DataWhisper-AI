import re
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

from app.config import get_settings
from app.schemas import (
    AnalyticalOperation,
    CollectionName,
    MongoQueryCandidate,
    PlannerFilter,
    QueryAttempt,
    QueryPlannerSchema,
    QueryRunResponse,
)


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _is_tests_scope(field_path: str) -> bool:
    """True if field_path belongs to the _tests collection."""
    if not field_path:
        return False
    if field_path.startswith("TestParametersFlat."):
        return True
    return field_path in {"name", "state", "testProgramId", "_id"}


_DATE_FIELD_TAILS = {"uploaddate", "date", "time", "timestamp", "modifiedon", "createdat"}


def _should_coerce_date(field_path: str) -> bool:
    tail = field_path.rstrip(".").split(".")[-1].lower()
    return tail in _DATE_FIELD_TAILS or tail.endswith("date") or tail.endswith("time")


def _coerce_date_value(value: Any) -> Any:
    """Convert relative/ISO date strings to Python datetime objects."""
    if not isinstance(value, str):
        return value

    token = value.strip().lower()
    if token in {"now", "today"}:
        return datetime.utcnow()

    compact = re.sub(r"\s+", "", token)
    rel = re.fullmatch(r"(?:now|today)-(\d+)(d|h|w|m|mo|month|months)", compact)
    if rel:
        amount, unit = int(rel.group(1)), rel.group(2)
        if unit == "d":
            return datetime.utcnow() - timedelta(days=amount)
        if unit == "h":
            return datetime.utcnow() - timedelta(hours=amount)
        if unit == "w":
            return datetime.utcnow() - timedelta(weeks=amount)
        if unit in {"m", "mo", "month", "months"}:
            return datetime.utcnow() - timedelta(days=amount * 30)

    spaced = re.fullmatch(r"(?:last|past)\s+(\d+)\s*(day|days|week|weeks|month|months|hour|hours)", token)
    if spaced:
        amount, unit = int(spaced.group(1)), spaced.group(2)
        if unit in {"day", "days"}:
            return datetime.utcnow() - timedelta(days=amount)
        if unit in {"week", "weeks"}:
            return datetime.utcnow() - timedelta(weeks=amount)
        if unit in {"month", "months"}:
            return datetime.utcnow() - timedelta(days=amount * 30)
        if unit in {"hour", "hours"}:
            return datetime.utcnow() - timedelta(hours=amount)

    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return value


def _build_match_from_planner_filters(
    filters: list[PlannerFilter],
    prefix: str = "",
) -> dict[str, Any]:
    """Convert PlannerFilter list to a MongoDB $match query dict."""
    match: dict[str, Any] = {}
    for f in filters:
        field = f"{prefix}{f.field_path}" if prefix else f.field_path
        val = f.value
        op = f.operator

        if _should_coerce_date(field):
            if isinstance(val, list):
                val = [_coerce_date_value(v) for v in val]
            else:
                val = _coerce_date_value(val)

        if op == "eq":
            match[field] = val
        elif op == "in":
            match[field] = {"$in": val if isinstance(val, list) else [val]}
        elif op == "gte":
            existing = match.get(field)
            if isinstance(existing, dict):
                existing["$gte"] = val
            else:
                match[field] = {"$gte": val}
        elif op == "lte":
            existing = match.get(field)
            if isinstance(existing, dict):
                existing["$lte"] = val
            else:
                match[field] = {"$lte": val}
        elif op == "regex":
            match[field] = {"$regex": str(val), "$options": "i"}
    return match


class MongoExecutor:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _physical_collection_name(self, logical: CollectionName) -> str:
        if logical == CollectionName.values:
            return self.settings.mongo_collection_values
        return self.settings.mongo_collection_tests

    def _get_database(self, client: MongoClient):  # type: ignore[return]
        if self.settings.mongo_db_name:
            return client[self.settings.mongo_db_name]
        user_dbs = [db for db in client.list_database_names() if db not in {"admin", "local", "config"}]
        if not user_dbs:
            raise RuntimeError("No user database found. Set MONGO_DB_NAME in .env.")
        return client[user_dbs[0]]

    # ------------------------------------------------------------------
    # Pipeline builders
    # ------------------------------------------------------------------

    def _build_values_pipeline(self, plan: QueryPlannerSchema) -> list[dict[str, Any]]:
        """Build an aggregation pipeline starting from the values collection."""
        pipeline: list[dict[str, Any]] = []
        op = plan.analytical_engine.operation
        grouping_dim = plan.analytical_engine.grouping_dimension

        # 1. Filter by metric UUID + canonical channel (e.g. "Force" not "Stress" or "ForcePerTiter")
        # childId format: {UUID}-Zwick.Unittable.{Channel}.{UUID}-Zwick.Unittable.{Channel}_Value
        if plan.data_resolution.metrics:
            channel_patterns: list[str] = []
            uuid_only_patterns: list[str] = []
            for m in plan.data_resolution.metrics:
                if not m.resolved_uuid:
                    continue
                if m.canonical_channel:
                    # Anchor with ^ so MongoDB can use the childId index for a range scan.
                    # childId always starts with {UUID}, so ^ is safe and correct.
                    channel_patterns.append(
                        r"^\{" + re.escape(m.resolved_uuid) + r"\}-Zwick\.Unittable\." + re.escape(m.canonical_channel) + r"\."
                    )
                else:
                    uuid_only_patterns.append(r"^\{?" + re.escape(m.resolved_uuid))

            all_patterns = channel_patterns + uuid_only_patterns
            if all_patterns:
                regex_pattern = "|".join(all_patterns)
                pipeline.append({
                    "$match": {"metadata.childId": {"$regex": regex_pattern, "$options": "i"}}
                })

        # 2. Apply value-scope filters (e.g., uploadDate ranges)
        value_filters = [f for f in plan.data_resolution.filters if not _is_tests_scope(f.field_path)]
        if value_filters:
            match = _build_match_from_planner_filters(value_filters)
            if match:
                pipeline.append({"$match": match})

        # 3. Lookup tests collection if needed for test-scope filters, grouping, or trend dates.
        # linear_regression always needs the join: uploadDate is the import date (same for all
        # docs) so TestParametersFlat.Date (the actual test date) is required for meaningful trends.
        test_filters = [f for f in plan.data_resolution.filters if _is_tests_scope(f.field_path)]
        grouping_needs_test = bool(grouping_dim) and _is_tests_scope(grouping_dim or "")
        needs_test_join = bool(test_filters) or grouping_needs_test or op == AnalyticalOperation.linear_regression

        if needs_test_join:
            pipeline.extend([
                {
                    "$lookup": {
                        "from": self.settings.mongo_collection_tests,
                        "localField": "metadata.refId",
                        "foreignField": "_id",
                        "as": "test",
                    }
                },
                {"$unwind": "$test"},
            ])
            if test_filters:
                match = _build_match_from_planner_filters(test_filters, prefix="test.")
                if match:
                    pipeline.append({"$match": match})

        # 4. Operation-specific aggregation stages
        if op in {
            AnalyticalOperation.welch_t_test,
            AnalyticalOperation.standard_deviation,
            AnalyticalOperation.iqr_outlier,
        }:
            # Compute per-document stats using array operators (avoids $unwind on huge arrays)
            pipeline.append({"$limit": 2000})
            # Strip NaN/null from values array before computing stats (NaN != NaN in IEEE 754)
            pipeline.append({"$project": {
                "_id": 1,
                "uploadDate": 1,
                "metadata": 1,
                "test": 1,
                "clean_values": {
                    "$filter": {
                        "input": "$values",
                        "as": "v",
                        "cond": {"$and": [
                            {"$isNumber": "$$v"},
                            {"$gt": ["$$v", -1e15]},
                            {"$lt": ["$$v", 1e15]},
                        ]},
                    }
                },
            }})
            pipeline.append({"$project": {
                "_id": 1,
                "uploadDate": 1,
                "metadata": 1,
                "test": 1,
                "doc_avg": {"$avg": "$clean_values"},
                "doc_min": {"$min": "$clean_values"},
                "doc_max": {"$max": "$clean_values"},
                "doc_std": {"$stdDevPop": "$clean_values"},
                "doc_count": {"$size": "$clean_values"},
            }})
            # Drop docs where doc_avg is null/NaN/Inf
            pipeline.append({"$match": {"$expr": {
                "$and": [
                    {"$gt": ["$doc_avg", -1e15]},
                    {"$lt": ["$doc_avg", 1e15]},
                ]
            }}})

            if grouping_dim:
                group_key: Any = f"$test.{grouping_dim}" if needs_test_join else f"${grouping_dim}"
            else:
                group_key = "all"

            pipeline.append({"$group": {
                "_id": group_key,
                "mean": {"$avg": "$doc_avg"},
                "stdDev": {"$avg": "$doc_std"},
                "count": {"$sum": "$doc_count"},
                "min": {"$min": "$doc_min"},
                "max": {"$max": "$doc_max"},
                "doc_count": {"$sum": 1},
            }})
            pipeline.append({"$sort": {"doc_count": -1}})
            pipeline.append({"$limit": 50})

        elif op == AnalyticalOperation.linear_regression:
            # Compute per-document average first (avoids $unwind on huge arrays)
            pipeline.append({"$limit": 5000})
            pipeline.append({"$project": {
                "uploadDate": 1,
                "metadata": 1,
                "test": 1,
                "clean_values": {
                    "$filter": {
                        "input": "$values",
                        "as": "v",
                        "cond": {"$and": [
                            {"$isNumber": "$$v"},
                            {"$gt": ["$$v", -1e15]},
                            {"$lt": ["$$v", 1e15]},
                        ]},
                    }
                },
            }})
            pipeline.append({"$project": {
                "uploadDate": 1,
                "metadata": 1,
                "test": 1,
                "doc_avg": {"$avg": "$clean_values"},
            }})
            # Drop docs where doc_avg is null/NaN/Inf
            pipeline.append({"$match": {"$expr": {"$and": [
                {"$gt": ["$doc_avg", -1e15]},
                {"$lt": ["$doc_avg", 1e15]},
            ]}}})
            # Group by time bucket.
            # Use the actual test date (TestParametersFlat.Date = "DD.MM.YYYY") when the
            # _tests join is present — uploadDate is the import date (same for all docs).
            # Fall back to uploadDate only when no join was performed.
            interval = plan.analytical_engine.time_series_interval or "week"
            if needs_test_join:
                # $dateFromString throws if the input is not a string (e.g. missing field,
                # ISODate object, number). Wrap in $convert→string first so the input to
                # $dateFromString is always a string or ""; then onError/onNull handle the rest.
                date_expr = {
                    "$dateFromString": {
                        "dateString": {
                            "$convert": {
                                "input": "$test.TestParametersFlat.Date",
                                "to": "string",
                                "onError": "",
                                "onNull": "",
                            }
                        },
                        "format": "%d.%m.%Y",
                        "onError": None,
                        "onNull": None,
                    }
                }
            else:
                # uploadDate is stored as a native ISODate — use it directly.
                date_expr = "$uploadDate"
            group_id: Any = {
                "date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d" if interval == "day" else "%Y-%W",
                        "date": date_expr,
                    }
                }
            }
            if grouping_dim:
                group_id["group"] = f"$test.{grouping_dim}" if needs_test_join else f"${grouping_dim}"

            pipeline.append({"$group": {
                "_id": group_id,
                "avg_value": {"$avg": "$doc_avg"},
                "count": {"$sum": 1},
            }})
            # Drop buckets where date parsed to null (missing/invalid date field)
            pipeline.append({"$match": {"_id.date": {"$ne": None}}})
            pipeline.append({"$sort": {"_id.date": 1}})
            pipeline.append({"$limit": min(500, self.settings.max_query_rows)})

        else:  # raw_fetch
            project: dict[str, Any] = {
                "_id": 0,
                "refId": "$metadata.refId",
                "childId": "$metadata.childId",
                "uploadDate": 1,
                "valuesCount": 1,
            }
            if needs_test_join:
                project["testName"] = "$test.name"
                if grouping_dim:
                    project["group"] = f"$test.{grouping_dim}"
            pipeline.append({"$project": project})
            pipeline.append({"$limit": min(200, self.settings.max_query_rows)})

        return pipeline

    def _build_tests_pipeline(self, plan: QueryPlannerSchema) -> list[dict[str, Any]]:
        """Build an aggregation pipeline starting from the tests collection."""
        pipeline: list[dict[str, Any]] = []
        op = plan.analytical_engine.operation
        grouping_dim = plan.analytical_engine.grouping_dimension

        # Apply test-scope filters
        test_filters = [f for f in plan.data_resolution.filters if _is_tests_scope(f.field_path)]
        if test_filters:
            match = _build_match_from_planner_filters(test_filters)
            if match:
                pipeline.append({"$match": match})

        # Group or project
        if op == AnalyticalOperation.count:
            pipeline.append({"$count": "total"})
        elif grouping_dim and op != AnalyticalOperation.raw_fetch:
            pipeline.append({"$group": {
                "_id": f"${grouping_dim}",
                "count": {"$sum": 1},
            }})
            pipeline.append({"$sort": {"count": -1}})
            pipeline.append({"$limit": min(200, self.settings.max_query_rows)})
        else:
            # raw_fetch: return clean minimal fields, not the full TestParametersFlat blob
            pipeline.append({"$project": {
                "_id": 1,
                "name": 1,
                "state": 1,
                "customer": "$TestParametersFlat.CUSTOMER",
                "material": "$TestParametersFlat.MATERIAL",
                "tester": "$TestParametersFlat.TESTER",
                "testType": "$TestParametersFlat.TYPE_OF_TESTING_STR",
                "standard": "$TestParametersFlat.STANDARD",
                "machine": "$TestParametersFlat.MACHINE_TYPE_STR",
            }})
            pipeline.append({"$limit": min(200, self.settings.max_query_rows)})
        return pipeline

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_candidate_from_query_plan(self, plan: QueryPlannerSchema) -> MongoQueryCandidate:
        """Deterministically build a MongoQueryCandidate from the QueryPlannerSchema."""
        needs_values = (
            "values" in plan.data_resolution.target_collections
            or bool(plan.data_resolution.metrics)
        )

        op = plan.analytical_engine.operation

        # COUNT always targets _tests — we are counting test records, not values.
        # Metrics in the plan are irrelevant for counting.
        if op == AnalyticalOperation.count:
            collection = CollectionName.tests
            pipeline = self._build_tests_pipeline(plan)
            expected_shape = ["total"]
        elif needs_values:
            collection = CollectionName.values
            pipeline = self._build_values_pipeline(plan)
            if op in {
                AnalyticalOperation.welch_t_test,
                AnalyticalOperation.standard_deviation,
                AnalyticalOperation.iqr_outlier,
            }:
                expected_shape = ["_id", "mean", "stdDev", "count", "min", "max"]
            elif op == AnalyticalOperation.linear_regression:
                expected_shape = ["_id.date", "avg_value", "count"]
            else:
                expected_shape = ["refId", "childId", "uploadDate", "valuesCount"]
        else:
            collection = CollectionName.tests
            pipeline = self._build_tests_pipeline(plan)
            if plan.analytical_engine.grouping_dimension:
                expected_shape = ["_id", "count"]
            else:
                expected_shape = ["_id", "name", "customer", "material", "testType", "standard"]

        return MongoQueryCandidate(
            collection=collection,
            pipeline=pipeline,
            explanation=(
                f"Programmatic pipeline for {plan.analytical_engine.operation.value} "
                f"on {plan.query_intent.value} intent."
            ),
            expected_shape=expected_shape,
        )

    def run_plan_with_repair(
        self,
        plan: QueryPlannerSchema,
        max_repairs: int | None = None,
        semantic_candidates: list | None = None,
    ) -> QueryRunResponse:
        """Alias used by main.py."""
        return self.run_plan(plan, max_repairs)

    def run_plan(
        self,
        plan: QueryPlannerSchema,
        max_repairs: int | None = None,
    ) -> QueryRunResponse:
        """Execute the query plan against MongoDB with automatic fallback recovery."""
        candidate = self.generate_candidate_from_query_plan(plan)
        attempts: list[QueryAttempt] = []

        with MongoClient(self.settings.mongo_uri, serverSelectionTimeoutMS=7000) as client:
            db = self._get_database(client)
            physical_name = self._physical_collection_name(candidate.collection)
            collection = db[physical_name]

            # Attempt 1: run the generated pipeline
            try:
                cursor = collection.aggregate(candidate.pipeline, allowDiskUse=True)
                rows = [_to_json_safe(row) for row in cursor]
                rows = rows[: self.settings.max_query_rows]

                attempts.append(QueryAttempt(
                    attempt=1,
                    pipeline=candidate.pipeline,
                    error=None,
                    corrected_from_previous=False,
                ))

                # If 0 rows, try stripping $match stages as last-resort fallback
                if len(rows) == 0:
                    stripped = [s for s in candidate.pipeline if "$match" not in s]
                    if stripped and stripped != candidate.pipeline:
                        try:
                            stripped_cursor = collection.aggregate(stripped, allowDiskUse=True)
                            stripped_rows = [_to_json_safe(r) for r in stripped_cursor]
                            stripped_rows = stripped_rows[: self.settings.max_query_rows]
                            if stripped_rows:
                                candidate.pipeline = stripped
                                attempts.append(QueryAttempt(
                                    attempt=2,
                                    pipeline=stripped,
                                    error=None,
                                    corrected_from_previous=True,
                                ))
                                return QueryRunResponse(
                                    status="success",
                                    candidate=candidate,
                                    attempts=attempts,
                                    row_count=len(stripped_rows),
                                    rows=stripped_rows,
                                    corrected_automatically=True,
                                )
                        except Exception:  # noqa: BLE001
                            pass

                return QueryRunResponse(
                    status="success",
                    candidate=candidate,
                    attempts=attempts,
                    row_count=len(rows),
                    rows=rows,
                    corrected_automatically=False,
                )

            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)
                attempts.append(QueryAttempt(
                    attempt=1,
                    pipeline=candidate.pipeline,
                    error=error_text,
                    corrected_from_previous=False,
                ))

                # Return empty rows — the insight engine will report "no data found".
                # Previously this ran a 50-test fallback fetch which returned irrelevant
                # test docs that the insight LLM mistakenly described as real answers.
                return QueryRunResponse(
                    status="failed",
                    candidate=candidate,
                    attempts=attempts,
                    row_count=0,
                    rows=[],
                    corrected_automatically=False,
                )
