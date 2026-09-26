from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.settings import get_settings
from app.routers import health, tickets, documents, feedback, audit, search, analytics

settings = get_settings()

app = FastAPI(
    title="SOLVIA API",
    description="Enterprise AI intelligence engine for SAP/IT support consultants.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
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


@app.get("/")
def root() -> dict:
    return {
        "service": "SOLVIA",
        "description": "Intelligent Solution Discovery for SAP/IT support consultants",
    }
