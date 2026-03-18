from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .services.semantic_mapper import SemanticMapper
from .services.stats_engine import StatsEngine
from .services.db_client import DatabaseClient

app = FastAPI(title="ZwickRoell Data Whisperer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Person 2: Global Instances ---
mapper = SemanticMapper()
stats = StatsEngine()
db = DatabaseClient()

class QueryRequest(BaseModel):
    natural_language_query: str

@app.get("/")
def read_root():
    return {
        "status": "Backend is running. Person 2 constraints met.",
        "mapped_terms": len(mapper.get_all_mappings())
    }

@app.post("/query")
async def process_query(req: QueryRequest):
    """
    Person 3's Domain:
    This endpoint takes the English query and processes it using the tools built by Person 2.
    It should:
    1. Plan the query (Planner LLM)
    2. Translate concepts (mapper.get_uuid_for_term())
    3. Generate the Mongo JSON Pipeline (Query LLM)
    4. Run it (await db.execute_raw_aggregation())
    5. Run statistical tests (stats.calculate_drift())
    6. Return the human explanation + chart rendering JSON (Insight LLM)
    """
    # Placeholder for Person 3's Integration
    return {"message": "Person 3 needs to connect the LangChain graph here!"}
