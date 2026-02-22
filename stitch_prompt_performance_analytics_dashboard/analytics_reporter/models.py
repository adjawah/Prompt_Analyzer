"""Pydantic models for dashboard data."""

from __future__ import annotations
from pydantic import BaseModel, Field


class DashboardOverview(BaseModel):
    """Top-level KPI data for the dashboard."""
    total_interactions: int = 0
    human_count: int = 0
    agent_count: int = 0
    avg_overall_score: float = 0.0
    avg_token_savings: float = 0.0
    rewrite_acceptance_rate: float = 0.0
    total_mistakes_found: int = 0


class TrendPoint(BaseModel):
    """A single point in a time-series trend."""
    date: str
    avg_score: float
    count: int


class MistakeFrequency(BaseModel):
    """How often a mistake type appears."""
    type: str
    count: int
    percentage: float


class AgentStats(BaseModel):
    """Stats for a single agent across all its interactions."""
    agent_id: str
    total_prompts: int = 0
    avg_score: float = 0.0
    weakest_dimension: str | None = None
    most_common_mistake: str | None = None
    improvement_trend: str = "—"  # ↑ ↓ —


class InteractionRow(BaseModel):
    """A single row in the interaction feed."""
    id: int
    timestamp: str
    source: str  # "human" or agent name
    target: str | None = None
    project_id: str | None = None
    prompt_preview: str
    overall_score: int
    clarity: int
    token_efficiency: int
    goal_alignment: int
    structure: int
    vagueness_index: int
    mistake_count: int
    token_savings: float
    rewrite_used: bool | None = None
