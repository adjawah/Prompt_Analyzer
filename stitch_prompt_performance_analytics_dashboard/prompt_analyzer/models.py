"""Pydantic models for prompt analysis data structures."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class Score(BaseModel):
    """A single dimension score with reasoning."""
    score: int = Field(ge=0, le=100, description="Score from 0-100")
    reasoning: str = Field(description="Brief explanation for the score")


class Mistake(BaseModel):
    """A specific mistake identified in the prompt."""
    type: str = Field(description="Category: vague_instruction, missing_context, redundancy, contradiction, poor_formatting, missing_output_format")
    text: Optional[str] = Field(default=None, description="The problematic text from the prompt, if applicable")
    suggestion: str = Field(description="How to fix this mistake")


class TokenComparison(BaseModel):
    """Token usage comparison between original and rewritten prompts."""
    original_tokens: int = Field(ge=0)
    rewritten_tokens: int = Field(ge=0)
    savings_percent: float = Field(description="Percentage of tokens saved")


class Scores(BaseModel):
    """All 5 analysis dimension scores."""
    clarity: Score
    token_efficiency: Score
    goal_alignment: Score
    structure: Score
    vagueness_index: Score


class AnalysisMetadata(BaseModel):
    """Metadata about who/what triggered the analysis."""
    project_id: Optional[str] = None
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: str = Field(default="human", description="'human' or 'agent'")


class AnalysisResult(BaseModel):
    """Complete analysis result returned by the Prompt Analyzer."""
    original_prompt: str
    overall_score: int = Field(ge=0, le=100)
    scores: Scores
    mistakes: list[Mistake] = Field(default_factory=list)
    rewritten_prompt: str
    token_comparison: TokenComparison
    metadata: AnalysisMetadata = Field(default_factory=AnalysisMetadata)


class AnalyzeRequest(BaseModel):
    """Request payload for prompt analysis."""
    prompt: str = Field(min_length=1, description="The prompt to analyze")
    context: Optional[str] = Field(default=None, description="Optional goal or context for the prompt")
    project_id: Optional[str] = Field(default=None, description="Project ID for context-aware analysis")
    source_agent: Optional[str] = Field(default=None, description="Agent that sent this prompt")
    target_agent: Optional[str] = Field(default=None, description="Agent this prompt is directed to")
