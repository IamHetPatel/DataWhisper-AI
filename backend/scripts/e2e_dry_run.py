"""End-to-end dry run: planner -> mongo executor -> insight generator.

Usage:
    python scripts/e2e_dry_run.py --question "Compare Company_1 vs Company_2 on maximum force"
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Make sure app/ is importable from the backend root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.insight import build_insight
from app.services.mongo_executor import MongoExecutor
from app.services.planner import build_plan


def _pretty(label: str, data: object) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print("=" * 60)
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


def run(question: str) -> None:
    print(f"\nQuestion: {question!r}")

    # ── 1. Planner ──────────────────────────────────────────────
    t0 = time.perf_counter()
    plan, semantic_candidates = build_plan(question)
    planner_ms = (time.perf_counter() - t0) * 1000

    _pretty(f"PLAN  ({planner_ms:.0f} ms)", plan.model_dump())

    # ── 2. MongoDB executor ──────────────────────────────────────
    t0 = time.perf_counter()
    executor = MongoExecutor()
    result = executor.run_plan(plan)
    query_ms = (time.perf_counter() - t0) * 1000

    status = result.status if result else "no result"
    rows = result.rows if result else []
    attempts = result.attempts if result else []

    print(f"\n{'='*60}")
    print(f"  QUERY RESULT  ({query_ms:.0f} ms)  status={status}  rows={len(rows)}")
    print("=" * 60)
    if attempts:
        for a in attempts:
            tag = " [corrected]" if a.corrected_from_previous else ""
            err = f"  error: {a.error}" if a.error else ""
            print(f"  attempt {a.attempt}{tag}{err}")
    if rows:
        print(f"\n  First {min(3, len(rows))} row(s):")
        for row in rows[:3]:
            print(f"    {json.dumps(row, default=str)}")
    else:
        print("  (no rows returned)")

    # ── 3. Insight generator ─────────────────────────────────────
    t0 = time.perf_counter()
    insight = build_insight(plan, rows, {})
    insight_ms = (time.perf_counter() - t0) * 1000

    _pretty(f"INSIGHT  ({insight_ms:.0f} ms)", insight.model_dump())

    total_ms = planner_ms + query_ms + insight_ms
    print(f"\nTotal wall time: {total_ms:.0f} ms\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end pipeline dry run")
    parser.add_argument(
        "--question",
        default="Compare Company_1 vs Company_2 on maximum force",
        help="Natural language question to process",
    )
    args = parser.parse_args()
    run(args.question)


if __name__ == "__main__":
    main()
