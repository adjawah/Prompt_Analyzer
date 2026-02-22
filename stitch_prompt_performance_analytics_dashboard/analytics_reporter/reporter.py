"""
Agent 2: Analytics Reporter

Receives analysis results from Agent 1 (Prompt Analyzer),
aggregates them, and stores them for the dashboard.
"""

import logging
from prompt_analyzer.models import AnalysisResult
from analytics_reporter import db

logger = logging.getLogger(__name__)


class AnalyticsReporter:
    """
    Collects analysis results, stores them in the database,
    and provides aggregated data for the dashboard.
    """

    async def initialize(self) -> None:
        """Initialize the database."""
        await db.init_db()
        logger.info("AnalyticsReporter initialized")

    async def report(self, result: AnalysisResult) -> int:
        """
        Process and store an analysis result.

        Args:
            result: The AnalysisResult from the Prompt Analyzer

        Returns:
            The database ID of the stored analysis
        """
        result_dict = result.model_dump(mode="json")
        analysis_id = await db.store_analysis(result_dict)
        logger.info(
            "Reported analysis id=%d score=%d project=%s",
            analysis_id,
            result.overall_score,
            result.metadata.project_id,
        )
        return analysis_id

    async def get_overview(self) -> dict:
        """Get dashboard overview KPIs."""
        return await db.get_overview_stats()

    async def get_interactions(
        self, limit: int = 50, offset: int = 0, project_id: str = None
    ) -> dict:
        """Get paginated interaction feed."""
        rows = await db.get_interactions(limit, offset, project_id)
        total = await db.get_total_count(project_id)
        return {
            "interactions": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_trends(self, days: int = 30, hours: int = None) -> list[dict]:
        """Get score trends over time."""
        return await db.get_trends(hours=hours, days=days)

    async def get_mistake_frequencies(self, limit: int = 10) -> list[dict]:
        """Get most common mistake types."""
        return await db.get_mistake_frequencies(limit)

    async def get_agent_leaderboard(self) -> list[dict]:
        """Get per-agent statistics."""
        return await db.get_agent_leaderboard()

    async def mark_rewrite_choice(self, analysis_id: int, used: bool) -> None:
        """Record whether the user chose the rewritten prompt."""
        await db.mark_rewrite_used(analysis_id, used)
        logger.info("Rewrite choice recorded: id=%d used=%s", analysis_id, used)
