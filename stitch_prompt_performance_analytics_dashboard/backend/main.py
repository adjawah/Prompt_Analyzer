"""
FastAPI backend — REST API for the Prompt Analyzer and Dashboard.

Serves:
- POST /analyze        → Human prompt analysis
- POST /rewrite-choice → Record rewrite acceptance
- GET  /dashboard/*    → Dashboard data endpoints
- GET  /health         → Health check
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from prompt_analyzer import PromptAnalyzer
from prompt_analyzer.models import AnalyzeRequest
from analytics_reporter.reporter import AnalyticsReporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Shared instances
analyzer = PromptAnalyzer()
reporter = AnalyticsReporter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    await reporter.initialize()
    logger.info("Backend ready")
    yield
    logger.info("Backend shutting down")


app = FastAPI(
    title="Prompt Performance Analytics",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend to call from any origin in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Analysis Endpoints ─────────────────────────────────────────


@app.post("/analyze")
async def analyze_prompt(request: AnalyzeRequest):
    """
    Analyze a prompt and return quality scores, mistakes, and rewrite.
    This is the main endpoint used by both the Web UI and external clients.
    """
    try:
        result = await analyzer.analyze(
            prompt=request.prompt,
            context=request.context,
            project_id=request.project_id,
            source_agent=request.source_agent,
            target_agent=request.target_agent,
        )

        # Agent 2: store the result for dashboard
        analysis_id = await reporter.report(result)

        # Return result with the DB id so frontend can track rewrite choice
        response = result.model_dump(mode="json")
        response["analysis_id"] = analysis_id
        return response

    except Exception as e:
        logger.error("Analysis failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


class RewriteChoiceRequest(BaseModel):
    analysis_id: int
    used_rewrite: bool


@app.post("/rewrite-choice")
async def record_rewrite_choice(request: RewriteChoiceRequest):
    """Record whether the user chose the rewritten prompt."""
    try:
        await reporter.mark_rewrite_choice(request.analysis_id, request.used_rewrite)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dashboard Endpoints ────────────────────────────────────────


@app.get("/dashboard/overview")
async def dashboard_overview():
    """Get dashboard KPI overview."""
    return await reporter.get_overview()


@app.get("/dashboard/interactions")
async def dashboard_interactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    project_id: Optional[str] = Query(default=None),
):
    """Get paginated interaction feed."""
    return await reporter.get_interactions(limit, offset, project_id)


@app.get("/dashboard/trends")
async def dashboard_trends(
    days: int = Query(default=30, ge=1, le=365),
    hours: Optional[int] = Query(default=None, ge=1, le=720),
):
    """Get quality score trends over time. Use hours for short ranges."""
    return await reporter.get_trends(days=days, hours=hours)


@app.get("/dashboard/mistakes")
async def dashboard_mistakes(limit: int = Query(default=10, ge=1, le=50)):
    """Get most common mistake types."""
    return await reporter.get_mistake_frequencies(limit)


@app.get("/dashboard/agents")
async def dashboard_agents():
    """Get agent leaderboard."""
    return await reporter.get_agent_leaderboard()


# ── Static files & Health ──────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


# Serve frontend static files
import os
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")

if os.path.isdir(frontend_dir):
    @app.get("/", response_class=FileResponse)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend")

if os.path.isdir(dashboard_dir):
    @app.get("/dashboard-ui", response_class=FileResponse)
    async def serve_dashboard():
        return FileResponse(os.path.join(dashboard_dir, "index.html"))

    app.mount("/dashboard-static", StaticFiles(directory=dashboard_dir), name="dashboard")
