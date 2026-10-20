from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, tickets, documents, feedback, audit, search, analytics, knowledge
from app.database import ensure_schema

ensure_schema()

app = FastAPI(
    title="SOLVIA API",
    description="Enterprise AI intelligence engine for SAP/IT support consultants.",
    version="1.0.0",
)

# Allow localhost, production Vercel domain, and any preview Vercel deployments
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "https://kabel-phi.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tickets.router)
app.include_router(documents.router)
app.include_router(feedback.router)
app.include_router(audit.router)
app.include_router(search.router)
app.include_router(analytics.router)
app.include_router(knowledge.router)


@app.get("/")
def root() -> dict:
    return {
        "service": "SOLVIA",
        "description": "Intelligent Solution Discovery for SAP/IT support consultants",
    }