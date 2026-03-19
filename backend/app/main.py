from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .schemas import (
    InsightRequest,
    InsightResponse,
    PlannerRequest,
    PlannerResponse,
    QueryRunRequest,
    QueryRunResponse,
)

# Person 2's Global Dependencies
from .services.semantic_mapper import SemanticMapper
from .services.stats_engine import StatsEngine
from .services.db_client import DatabaseClient

# Person 3's LLM Handlers (To be implemented by Person 3)
try:
    from .services.insight import build_insight
    from .services.mongo_executor import MongoExecutor
    from .services.planner import build_plan
except ImportError:
    # Fallback placeholders in case Person 3 hasn't committed their files yet
    def build_plan(*args, **kwargs): return None, []
    def build_insight(*args, **kwargs): return None
    class MongoExecutor:
        def run_plan_with_repair(self, *args, **kwargs): return None

settings = get_settings()
app = FastAPI(title="ZwickRoell Data Whisperer API - Merged")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "anthropic_ready": "yes" if bool(settings.anthropic_api_key) else "no",
        "mapped_terms_count": str(len(mapper.get_all_mappings()))
    }


@app.post("/planner/plan", response_model=PlannerResponse)
def planner_plan(payload: PlannerRequest) -> PlannerResponse:
    plan, semantic_candidates = build_plan(payload.question, payload.context)
    return PlannerResponse(plan=plan, semantic_candidates=semantic_candidates)


@app.post("/query/run", response_model=QueryRunResponse)
def query_run(payload: QueryRunRequest) -> QueryRunResponse:
    candidates = payload.semantic_candidates or None
    return executor.run_plan_with_repair(payload.plan, payload.max_repairs, semantic_candidates=candidates)


@app.post("/insight/generate", response_model=InsightResponse)
def insight_generate(payload: InsightRequest) -> InsightResponse:
    # Here Person 3 can wire up Person 2's stats_engine using the data!
    return build_insight(payload.plan, payload.rows, payload.stats)
