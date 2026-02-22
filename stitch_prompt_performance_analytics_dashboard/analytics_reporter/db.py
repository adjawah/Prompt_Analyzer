"""SQLite database for storing analysis results and aggregations."""

import aiosqlite
import json
import logging
import os
from typing import Optional

from prompt_analyzer.config import ANALYTICS_DB_PATH

logger = logging.getLogger(__name__)

# Use DB_PATH from environment if provided (useful for Render persistent disks), otherwise default to local file
DB_PATH = os.getenv("DB_PATH", "analytics.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'human',
    source_agent TEXT,
    target_agent TEXT,
    project_id TEXT,
    original_prompt TEXT NOT NULL,
    rewritten_prompt TEXT,
    overall_score INTEGER NOT NULL DEFAULT 0,
    clarity INTEGER NOT NULL DEFAULT 0,
    token_efficiency INTEGER NOT NULL DEFAULT 0,
    goal_alignment INTEGER NOT NULL DEFAULT 0,
    structure INTEGER NOT NULL DEFAULT 0,
    vagueness_index INTEGER NOT NULL DEFAULT 0,
    mistake_count INTEGER NOT NULL DEFAULT 0,
    mistakes_json TEXT,
    original_tokens INTEGER NOT NULL DEFAULT 0,
    rewritten_tokens INTEGER NOT NULL DEFAULT 0,
    token_savings_percent REAL NOT NULL DEFAULT 0.0,
    rewrite_used INTEGER,
    full_result_json TEXT
);
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_timestamp ON analyses(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_project ON analyses(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_source ON analyses(source_agent);",
]


async def init_db():
    """Initialize the database and create tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEX_SQL:
            await db.execute(idx_sql)
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def store_analysis(result_dict: dict) -> int:
    """Store an analysis result and return its ID."""
    scores = result_dict.get("scores", {})
    meta = result_dict.get("metadata", {})
    tc = result_dict.get("token_comparison", {})

    def _get_score(dim: str) -> int:
        val = scores.get(dim, {})
        if isinstance(val, dict):
            return val.get("score", 0)
        return 0

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO analyses (
                timestamp, mode, source_agent, target_agent, project_id,
                original_prompt, rewritten_prompt,
                overall_score, clarity, token_efficiency, goal_alignment,
                structure, vagueness_index,
                mistake_count, mistakes_json,
                original_tokens, rewritten_tokens, token_savings_percent,
                full_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meta.get("timestamp", ""),
                meta.get("mode", "human"),
                meta.get("source_agent"),
                meta.get("target_agent"),
                meta.get("project_id"),
                result_dict.get("original_prompt", ""),
                result_dict.get("rewritten_prompt", ""),
                result_dict.get("overall_score", 0),
                _get_score("clarity"),
                _get_score("token_efficiency"),
                _get_score("goal_alignment"),
                _get_score("structure"),
                _get_score("vagueness_index"),
                len(result_dict.get("mistakes", [])),
                json.dumps(result_dict.get("mistakes", []), default=str),
                tc.get("original_tokens", 0),
                tc.get("rewritten_tokens", 0),
                tc.get("savings_percent", 0.0),
                json.dumps(result_dict, default=str),
            ),
        )
        await db.commit()
        row_id = cursor.lastrowid
        logger.info("Stored analysis id=%d", row_id)
        return row_id


async def get_interactions(
    limit: int = 50,
    offset: int = 0,
    project_id: Optional[str] = None,
) -> list[dict]:
    """Get paginated interaction rows."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if project_id:
            cursor = await db.execute(
                "SELECT * FROM analyses WHERE project_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (project_id, limit, offset),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM analyses ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_total_count(project_id: Optional[str] = None) -> int:
    """Get total interaction count."""
    async with aiosqlite.connect(DB_PATH) as db:
        if project_id:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM analyses WHERE project_id = ?",
                (project_id,),
            )
        else:
            cursor = await db.execute("SELECT COUNT(*) FROM analyses")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_overview_stats() -> dict:
    """Get aggregate stats for the dashboard overview."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN mode = 'human' THEN 1 ELSE 0 END) as human_count,
                SUM(CASE WHEN mode = 'agent' THEN 1 ELSE 0 END) as agent_count,
                AVG(overall_score) as avg_score,
                AVG(token_savings_percent) as avg_savings,
                SUM(mistake_count) as total_mistakes,
                SUM(CASE WHEN rewrite_used = 1 THEN 1 ELSE 0 END) as rewrites_used,
                SUM(CASE WHEN rewrite_used IS NOT NULL THEN 1 ELSE 0 END) as rewrites_decided,
                SUM(original_tokens) as total_tokens,
                AVG(original_tokens) as avg_tokens
            FROM analyses
        """)
        row = await cursor.fetchone()
        if not row or row[0] == 0:
            return {
                "total_interactions": 0,
                "human_count": 0,
                "agent_count": 0,
                "avg_overall_score": 0,
                "avg_token_savings": 0,
                "rewrite_acceptance_rate": 0,
                "total_mistakes_found": 0,
                "total_tokens": 0,
                "avg_tokens_per_prompt": 0,
            }
        return {
            "total_interactions": row[0],
            "human_count": row[1] or 0,
            "agent_count": row[2] or 0,
            "avg_overall_score": round(row[3] or 0, 1),
            "avg_token_savings": round(row[4] or 0, 1),
            "rewrite_acceptance_rate": round(
                (row[5] / row[6] * 100) if row[6] and row[6] > 0 else 0, 1
            ),
            "total_mistakes_found": row[7] or 0,
            "total_tokens": row[8] or 0,
            "avg_tokens_per_prompt": round(row[9] or 0, 1),
        }


async def get_trends(hours: int = None, days: int = 30) -> list[dict]:
    """Get score trends over time. If hours is set, group by hour; otherwise by day."""
    async with aiosqlite.connect(DB_PATH) as db:
        if hours is not None:
            # Group by hour for short time ranges
            cursor = await db.execute(
                """
                SELECT
                    strftime('%Y-%m-%d %H:00', timestamp) as period,
                    AVG(overall_score) as avg_score,
                    COUNT(*) as count
                FROM analyses
                WHERE timestamp >= datetime('now', ?)
                GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
                ORDER BY period ASC
                """,
                (f"-{hours} hours",),
            )
        else:
            # Group by day for longer ranges
            cursor = await db.execute(
                """
                SELECT
                    DATE(timestamp) as period,
                    AVG(overall_score) as avg_score,
                    COUNT(*) as count
                FROM analyses
                WHERE timestamp >= datetime('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY period ASC
                """,
                (f"-{days} days",),
            )
        rows = await cursor.fetchall()
        return [
            {"date": row[0], "avg_score": round(row[1], 1), "count": row[2]}
            for row in rows
        ]


async def get_mistake_frequencies(limit: int = 10) -> list[dict]:
    """Get the most common mistake types."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT mistakes_json FROM analyses WHERE mistakes_json IS NOT NULL")
        rows = await cursor.fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        try:
            mistakes = json.loads(row[0])
            for m in mistakes:
                mt = m.get("type", "unknown")
                counts[mt] = counts.get(mt, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue

    total = sum(counts.values()) or 1
    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    return [
        {"type": k, "count": v, "percentage": round(v / total * 100, 1)}
        for k, v in sorted_counts
    ]


async def get_agent_leaderboard() -> list[dict]:
    """Get per-agent statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                source_agent,
                COUNT(*) as total_prompts,
                AVG(overall_score) as avg_score
            FROM analyses
            WHERE source_agent IS NOT NULL
            GROUP BY source_agent
            ORDER BY avg_score DESC
        """)
        rows = await cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            "agent_id": row[0],
            "total_prompts": row[1],
            "avg_score": round(row[2], 1),
            "weakest_dimension": None,
            "most_common_mistake": None,
            "improvement_trend": "—",
        })
    return results


async def mark_rewrite_used(analysis_id: int, used: bool) -> None:
    """Mark whether the user chose the rewritten prompt."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE analyses SET rewrite_used = ? WHERE id = ?",
            (1 if used else 0, analysis_id),
        )
        await db.commit()
