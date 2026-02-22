"""
Prompt Analyzer — AI-powered prompt quality analysis.

Usage:
    from prompt_analyzer import PromptAnalyzer
    analyzer = PromptAnalyzer()
    result = await analyzer.analyze("Your prompt here")
"""

from prompt_analyzer.analyzer import PromptAnalyzer
from prompt_analyzer.models import (
    AnalysisResult,
    AnalyzeRequest,
    Scores,
    Score,
    Mistake,
    TokenComparison,
    AnalysisMetadata,
)

__version__ = "0.1.0"

__all__ = [
    "PromptAnalyzer",
    "AnalysisResult",
    "AnalyzeRequest",
    "Scores",
    "Score",
    "Mistake",
    "TokenComparison",
    "AnalysisMetadata",
]
