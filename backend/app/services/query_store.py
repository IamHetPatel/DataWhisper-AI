"""Persistent store for saved queries / reusable templates in MongoDB."""

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient

from app.config import get_settings

_log = logging.getLogger(__name__)

_COLLECTION = "saved_queries"


def _get_collection():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    db = client[settings.mongo_db_name] if settings.mongo_db_name else client.get_default_database()
    return client, db[_COLLECTION]


def save_query(
    question: str,
    intent: str,
    row_count: int,
    x_values: list[Any],
    y_values: list[Any],
    plan_dict: dict[str, Any],
) -> str | None:
    """Persist a successful query as a reusable template. Returns inserted id."""
    try:
        client, coll = _get_collection()
        with client:
            doc = {
                "question": question,
                "intent": intent,
                "row_count": row_count,
                "x_values": x_values[:50],   # cap to keep docs small
                "y_values": y_values[:50],
                "plan": plan_dict,
                "created_at": datetime.now(timezone.utc),
            }
            result = coll.insert_one(doc)
            return str(result.inserted_id)
    except Exception as exc:  # noqa: BLE001
        _log.warning("save_query failed: %s", exc)
        return None


def list_templates(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent saved queries, newest first."""
    try:
        client, coll = _get_collection()
        with client:
            cursor = coll.find({}, {"plan": 0}).sort("created_at", -1).limit(limit)
            results = []
            for doc in cursor:
                results.append({
                    "id": str(doc["_id"]),
                    "question": doc.get("question", ""),
                    "intent": doc.get("intent", ""),
                    "created_at": doc.get("created_at", datetime.now(timezone.utc)).isoformat(),
                    "row_count": doc.get("row_count", 0),
                    "x_values": doc.get("x_values", []),
                    "y_values": doc.get("y_values", []),
                })
            return results
    except Exception as exc:  # noqa: BLE001
        _log.warning("list_templates failed: %s", exc)
        return []
