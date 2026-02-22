"""
Core Prompt Analyzer agent.

Takes a prompt, calls Claude via the Anthropic API, and returns
structured analysis: scores, mistakes, rewritten prompt, and token comparison.
"""

import json
import logging
from typing import Optional

import tiktoken

from prompt_analyzer.anthropic_client import AnthropicClient
from prompt_analyzer.context_store import ContextStore
from prompt_analyzer.models import (
    AnalysisResult,
    AnalysisMetadata,
    Scores,
    Score,
    Mistake,
    TokenComparison,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Prompt Quality Analyzer. Your job is to analyze a given prompt and return a structured JSON assessment.

ANALYZE THE PROMPT ON THESE 5 DIMENSIONS (score each 0-100):

1. **Clarity** (0-100): How unambiguous is the prompt? Can it be misinterpreted? Are instructions precise?
2. **Token Efficiency** (0-100): How concise is the prompt? Are there redundant words, repeated instructions, or unnecessary filler? Higher = more efficient.
3. **Goal Alignment** (0-100): Does the prompt clearly state what output is expected? Is the desired result format, length, and style specified?
4. **Structure** (0-100): Is the prompt well-organized? Does it have logical flow, proper sections, and clear instruction ordering?
5. **Vagueness Index** (0-100): How many vague/ambiguous phrases exist? ("make it good", "do something nice", "be creative"). Score 0 = extremely vague, 100 = no vagueness at all.

ALSO:
- **Identify specific mistakes** in the prompt. For each mistake, provide:
  - `type`: one of: vague_instruction, missing_context, redundancy, contradiction, poor_formatting, missing_output_format, unclear_scope, overly_complex
  - `text`: the exact problematic text from the prompt (null if the mistake is about something missing)
  - `suggestion`: a concrete fix

- **Rewrite the prompt** to be optimal — maximum clarity, minimum tokens, best structure. The rewrite should accomplish the exact same goal as the original.

{project_context}

RESPOND WITH ONLY VALID JSON in this exact format (no markdown, no code fences, just the JSON):
{{
  "overall_score": <number 0-100, weighted average: clarity 25%, token_efficiency 20%, goal_alignment 25%, structure 15%, vagueness_index 15%>,
  "scores": {{
    "clarity": {{ "score": <0-100>, "reasoning": "<1-2 sentences>" }},
    "token_efficiency": {{ "score": <0-100>, "reasoning": "<1-2 sentences>" }},
    "goal_alignment": {{ "score": <0-100>, "reasoning": "<1-2 sentences>" }},
    "structure": {{ "score": <0-100>, "reasoning": "<1-2 sentences>" }},
    "vagueness_index": {{ "score": <0-100>, "reasoning": "<1-2 sentences>" }}
  }},
  "mistakes": [
    {{ "type": "<type>", "text": "<problematic text or null>", "suggestion": "<fix>" }}
  ],
  "rewritten_prompt": "<the optimized version of the prompt>"
}}"""


class PromptAnalyzer:
    """
    AI-powered prompt quality analyzer.

    Usage:
        analyzer = PromptAnalyzer()
        result = await analyzer.analyze("Your prompt here")

    For context-aware analysis (enterprise):
        result = await analyzer.analyze(
            prompt="...",
            project_id="customer_support",
            source_agent="planner",
        )
    """

    def __init__(self):
        self.llm = AnthropicClient()
        self.context_store = ContextStore()
        # Use cl100k_base tokenizer (closest to Claude's tokenization)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
            logger.warning("tiktoken not available, token counts will be estimated")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Rough estimate: ~4 chars per token
        return len(text) // 4

    async def analyze(
        self,
        prompt: str,
        context: Optional[str] = None,
        project_id: Optional[str] = None,
        source_agent: Optional[str] = None,
        target_agent: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Analyze a prompt and return structured quality assessment.

        Args:
            prompt: The prompt to analyze
            context: Optional goal/context for the prompt
            project_id: Optional project ID for context-aware analysis
            source_agent: Optional agent that authored this prompt
            target_agent: Optional agent this prompt is directed to

        Returns:
            AnalysisResult with scores, mistakes, and rewritten prompt
        """
        logger.info(
            "Analyzing prompt (length=%d, project=%s, agent=%s)",
            len(prompt),
            project_id,
            source_agent,
        )

        # Build context-aware system prompt
        project_context = self.context_store.build_context_summary(
            project_id, source_agent
        )
        system_prompt = SYSTEM_PROMPT.format(project_context=project_context)

        # Build user message
        user_message = self._build_user_message(prompt, context)

        # Call Gemini
        raw_response = await self.llm.invoke(system_prompt, user_message)

        # Parse the JSON response
        result = self._parse_response(raw_response, prompt, project_id, source_agent, target_agent)

        # Update context store (if project-aware)
        if project_id:
            analysis_dict = result.model_dump()
            self.context_store.append_history(project_id, analysis_dict)
            self.context_store.update_patterns(project_id, analysis_dict)
            if source_agent:
                self.context_store.update_agent_context(
                    project_id, source_agent, analysis_dict
                )

        return result

    def _build_user_message(
        self, prompt: str, context: Optional[str] = None
    ) -> str:
        """Build the user message sent to Claude."""
        parts = ["PROMPT TO ANALYZE:\n---"]
        parts.append(prompt)
        parts.append("---")

        if context:
            parts.append(f"\nCONTEXT/GOAL: {context}")

        return "\n".join(parts)

    def _extract_json(self, raw: str) -> str:
        """Extract JSON from Claude's response, handling various formatting."""
        import re

        cleaned = raw.strip()

        # 1. Remove markdown code fences (```json ... ``` or ``` ... ```)
        fence_pattern = re.compile(r'```(?:json)?\s*\n?(.*?)\n?\s*```', re.DOTALL)
        match = fence_pattern.search(cleaned)
        if match:
            cleaned = match.group(1).strip()

        # 2. If the response doesn't start with {, try to find the JSON object
        if not cleaned.startswith("{"):
            brace_start = cleaned.find("{")
            if brace_start != -1:
                cleaned = cleaned[brace_start:]

        # 3. Find the matching closing brace
        if cleaned.startswith("{"):
            depth = 0
            in_string = False
            escape = False
            end_pos = len(cleaned)
            for i, ch in enumerate(cleaned):
                if escape:
                    escape = False
                    continue
                if ch == '\\' and in_string:
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break
            cleaned = cleaned[:end_pos]

        # 4. Fix trailing commas before } or ] (common LLM mistake)
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

        return cleaned

    def _parse_response(
        self,
        raw: str,
        original_prompt: str,
        project_id: Optional[str],
        source_agent: Optional[str],
        target_agent: Optional[str],
    ) -> AnalysisResult:
        """Parse Claude's JSON response into an AnalysisResult."""
        cleaned = self._extract_json(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            logger.error("Raw response (first 500 chars): %s", raw[:500])
            logger.error("Cleaned response (first 500 chars): %s", cleaned[:500])
            # Return a fallback result
            return self._fallback_result(original_prompt, str(e), project_id, source_agent, target_agent)

        # Build structured result
        try:
            scores_data = data.get("scores", {})
            scores = Scores(
                clarity=Score(**scores_data.get("clarity", {"score": 0, "reasoning": "N/A"})),
                token_efficiency=Score(**scores_data.get("token_efficiency", {"score": 0, "reasoning": "N/A"})),
                goal_alignment=Score(**scores_data.get("goal_alignment", {"score": 0, "reasoning": "N/A"})),
                structure=Score(**scores_data.get("structure", {"score": 0, "reasoning": "N/A"})),
                vagueness_index=Score(**scores_data.get("vagueness_index", {"score": 0, "reasoning": "N/A"})),
            )

            mistakes = [
                Mistake(**m) for m in data.get("mistakes", [])
            ]

            rewritten = data.get("rewritten_prompt", original_prompt)
            original_tokens = self._count_tokens(original_prompt)
            rewritten_tokens = self._count_tokens(rewritten)
            savings = (
                round((1 - rewritten_tokens / original_tokens) * 100, 1)
                if original_tokens > 0
                else 0.0
            )

            return AnalysisResult(
                original_prompt=original_prompt,
                overall_score=data.get("overall_score", 0),
                scores=scores,
                mistakes=mistakes,
                rewritten_prompt=rewritten,
                token_comparison=TokenComparison(
                    original_tokens=original_tokens,
                    rewritten_tokens=rewritten_tokens,
                    savings_percent=savings,
                ),
                metadata=AnalysisMetadata(
                    project_id=project_id,
                    source_agent=source_agent,
                    target_agent=target_agent,
                    mode="agent" if source_agent else "human",
                ),
            )

        except Exception as e:
            logger.error("Failed to build AnalysisResult: %s", e)
            return self._fallback_result(original_prompt, str(e), project_id, source_agent, target_agent)

    def _fallback_result(
        self,
        prompt: str,
        error: str,
        project_id: Optional[str],
        source_agent: Optional[str],
        target_agent: Optional[str],
    ) -> AnalysisResult:
        """Return a fallback result when parsing fails."""
        fallback_score = Score(score=0, reasoning=f"Analysis failed: {error}")
        return AnalysisResult(
            original_prompt=prompt,
            overall_score=0,
            scores=Scores(
                clarity=fallback_score,
                token_efficiency=fallback_score,
                goal_alignment=fallback_score,
                structure=fallback_score,
                vagueness_index=fallback_score,
            ),
            mistakes=[
                Mistake(
                    type="analysis_error",
                    text=None,
                    suggestion=f"Re-run analysis. Error: {error}",
                )
            ],
            rewritten_prompt=prompt,
            token_comparison=TokenComparison(
                original_tokens=self._count_tokens(prompt),
                rewritten_tokens=self._count_tokens(prompt),
                savings_percent=0.0,
            ),
            metadata=AnalysisMetadata(
                project_id=project_id,
                source_agent=source_agent,
                target_agent=target_agent,
                mode="agent" if source_agent else "human",
            ),
        )
