from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ZwickRoell Data Whisperer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "Backend is running. Person 2 is ready to build endpoints!"}

# TODO: Add endpoints for:
# - POST /query (Takes NLP text -> returns AI insight + Chart config)
# - GET /history (Queries run history for Audit Trail)
# - POST /report (Generate Living Report)
