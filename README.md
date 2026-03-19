# START-Hack 2026

AI-powered data analytics dashboard with natural language query capabilities.

## Overview

This project provides an intelligent data exploration interface that allows users to ask questions about their data in plain language. The system leverages LLMs to:
- Understand user queries and create execution plans
- Map semantic concepts to database fields
- Execute queries against MongoDB
- Generate human-readable insights and visualizations

## Tech Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **Radix UI** for accessible components
- **Recharts** for data visualization
- **TanStack Query** for data fetching

### Backend
- **Python FastAPI**
- **MongoDB** for data storage
- **LLM Gateway** for AI integration (OpenAI-compatible)

## Project Structure

```
├── frontend/               # React frontend application
│   ├── src/
│   │   ├── components/    # UI components
│   │   │   ├── dashboard/ # Dashboard-specific components
│   │   │   └── ui/        # Reusable UI components (shadcn)
│   │   ├── pages/         # Page components
│   │   ├── hooks/         # Custom React hooks
│   │   └── lib/           # Utilities
│   └── package.json
│
├── backend/               # Python FastAPI backend
│   ├── app/
│   │   ├── services/      # Business logic
│   │   │   ├── insight.py       # LLM insight generation
│   │   │   ├── planner.py       # Query planning
│   │   │   ├── semantic_mapper.py # Field mapping
│   │   │   ├── mongo_executor.py # DB execution
│   │   │   ├── stats_engine.py  # Statistics
│   │   │   └── llm_gateway.py   # LLM client
│   │   ├── schemas.py    # API schemas
│   │   └── main.py       # FastAPI app
│   └── requirements.txt
│
├── INTEGRATION_GUIDE.md   # Hackathon integration guide
└── README.md
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB instance

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Configure environment variables (see `.env.example`):
- `OPENAI_API_KEY` - LLM access
- `MONGODB_URI` - Database connection
- Other settings in `backend/app/config.py`

```bash
uvicorn app.main:app --reload
```

The API runs on `http://localhost:8000`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/query` | POST | Full orchestration (plan → run → insight) |
| `/planner/plan` | POST | Create query plan from question |
| `/query/run` | POST | Execute planned query |
| `/insight/generate` | POST | Generate insight from results |

## Features

- **Natural Language Queries**: Ask questions in plain English
- **Semantic Mapping**: Automatic field mapping using LLM
- **Visual Charts**: Interactive data visualizations
- **Reasoning Display**: See how the AI interprets your query
- **Report Generation**: Export analysis results