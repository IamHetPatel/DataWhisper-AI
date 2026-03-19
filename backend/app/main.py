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
    """
    Master Orchestration Endpoint for the Frontend.
    Chains the Plan -> Run -> Insight flow together.
    """
    plan, candidates = build_plan(req.question, req.context)
    
    # Execute the MongoDB search with Plan
    run_resp = executor.run_plan(plan, settings.max_query_repairs)
    
    # Mocking stats momentarily until LLM properly builds it
    stats_output = {} 
    
    # Generate human textual explanation
    final_insight = build_insight(plan, run_resp.rows, stats_output)
    return final_insight
