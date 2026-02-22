"""
Per-project context store with strict isolation.

Each project gets its own directory. Context from one project
is never read or written by another project's operations.
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from prompt_analyzer.config import CONTEXT_STORE_DIR

logger = logging.getLogger(__name__)


class ContextStore:
    """Manages per-project context with strict isolation."""

    def __init__(self, base_dir: str = CONTEXT_STORE_DIR):
        self.base_dir = base_dir

    # ── Path helpers (always scoped to a project) ──────────────

    def _project_dir(self, project_id: str) -> str:
        """Get the isolated directory for a specific project."""
        safe_name = project_id.replace("/", "_").replace("..", "_")
        return os.path.join(self.base_dir, f"project_{safe_name}")

    def _profile_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "profile.json")

    def _history_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "history.jsonl")

    def _patterns_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "patterns.json")

    def _agent_path(self, project_id: str, agent_id: str) -> str:
        safe_agent = agent_id.replace("/", "_").replace("..", "_")
        return os.path.join(
            self._project_dir(project_id), "agents", f"{safe_agent}.json"
        )

    def _ensure_dir(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    # ── Project profile ────────────────────────────────────────

    def get_project_profile(self, project_id: str) -> dict:
        """Load project profile. Returns empty dict if project is new."""
        path = self._profile_path(project_id)
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)

    def save_project_profile(self, project_id: str, profile: dict) -> None:
        """Save or update a project profile."""
        path = self._profile_path(project_id)
        self._ensure_dir(path)
        with open(path, "w") as f:
            json.dump(profile, f, indent=2, default=str)
        logger.info("Saved profile for project=%s", project_id)

    # ── Analysis history (append-only log) ─────────────────────

    def append_history(self, project_id: str, analysis: dict) -> None:
        """Append an analysis result to the project's history."""
        path = self._history_path(project_id)
        self._ensure_dir(path)
        entry = {
            **analysis,
            "_stored_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        logger.debug("Appended history for project=%s", project_id)

    def get_recent_history(
        self, project_id: str, limit: int = 20
    ) -> list[dict]:
        """Get the most recent analyses for a project."""
        path = self._history_path(project_id)
        if not os.path.exists(path):
            return []
        entries = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]

    # ── Learned patterns ───────────────────────────────────────

    def get_patterns(self, project_id: str) -> dict:
        """
        Get learned patterns for a project:
        - common_mistakes: list of frequently seen mistake types
        - best_templates: high-scoring prompt excerpts
        - preferred_style: inferred preferences
        """
        path = self._patterns_path(project_id)
        if not os.path.exists(path):
            return {"common_mistakes": [], "best_templates": [], "preferred_style": ""}
        with open(path, "r") as f:
            return json.load(f)

    def update_patterns(self, project_id: str, analysis: dict) -> None:
        """Update learned patterns based on a new analysis result."""
        patterns = self.get_patterns(project_id)

        # Track mistake frequencies
        mistake_types = [m.get("type", "unknown") for m in analysis.get("mistakes", [])]
        existing_mistakes = {m["type"]: m.get("count", 0) for m in patterns.get("common_mistakes", []) if isinstance(m, dict)}
        for mt in mistake_types:
            existing_mistakes[mt] = existing_mistakes.get(mt, 0) + 1
        patterns["common_mistakes"] = [
            {"type": k, "count": v}
            for k, v in sorted(existing_mistakes.items(), key=lambda x: -x[1])
        ][:10]  # keep top 10

        # Track best-scoring prompts as templates
        overall_score = analysis.get("overall_score", 0)
        if overall_score >= 85:
            rewritten = analysis.get("rewritten_prompt", "")
            if rewritten:
                templates = patterns.get("best_templates", [])
                templates.append(
                    {"prompt": rewritten[:500], "score": overall_score}
                )
                # Keep top 5 by score
                templates.sort(key=lambda x: -x["score"])
                patterns["best_templates"] = templates[:5]

        path = self._patterns_path(project_id)
        self._ensure_dir(path)
        with open(path, "w") as f:
            json.dump(patterns, f, indent=2, default=str)

    # ── Per-agent context (within a project) ───────────────────

    def get_agent_context(
        self, project_id: str, agent_id: str
    ) -> dict:
        """Get an agent's context within a specific project."""
        path = self._agent_path(project_id, agent_id)
        if not os.path.exists(path):
            return {
                "agent_id": agent_id,
                "total_analyses": 0,
                "avg_score": 0,
                "common_mistakes": [],
                "weakest_dimension": None,
            }
        with open(path, "r") as f:
            return json.load(f)

    def update_agent_context(
        self, project_id: str, agent_id: str, analysis: dict
    ) -> None:
        """Update an agent's context within a project after analysis."""
        ctx = self.get_agent_context(project_id, agent_id)

        # Update running average score
        n = ctx["total_analyses"]
        old_avg = ctx["avg_score"]
        new_score = analysis.get("overall_score", 0)
        ctx["total_analyses"] = n + 1
        ctx["avg_score"] = round((old_avg * n + new_score) / (n + 1), 1)

        # Track agent-specific mistakes
        mistake_types = [m.get("type", "unknown") for m in analysis.get("mistakes", [])]
        existing = {m["type"]: m.get("count", 0) for m in ctx.get("common_mistakes", []) if isinstance(m, dict)}
        for mt in mistake_types:
            existing[mt] = existing.get(mt, 0) + 1
        ctx["common_mistakes"] = [
            {"type": k, "count": v}
            for k, v in sorted(existing.items(), key=lambda x: -x[1])
        ][:5]

        # Find weakest dimension
        scores = analysis.get("scores", {})
        if scores:
            if isinstance(scores, dict):
                weakest = min(
                    scores.items(),
                    key=lambda x: x[1].get("score", 100) if isinstance(x[1], dict) else x[1],
                )
                ctx["weakest_dimension"] = weakest[0]

        path = self._agent_path(project_id, agent_id)
        self._ensure_dir(path)
        with open(path, "w") as f:
            json.dump(ctx, f, indent=2, default=str)
        logger.debug(
            "Updated agent context: project=%s agent=%s", project_id, agent_id
        )

    # ── Build context summary for Claude's system prompt ───────

    def build_context_summary(
        self,
        project_id: Optional[str],
        source_agent: Optional[str] = None,
    ) -> str:
        """
        Build a context summary string to inject into Claude's system prompt.
        Only loads data from the specified project (strict isolation).
        Returns empty string if no project_id is provided.
        """
        if not project_id:
            return ""

        parts = []

        # Project profile
        profile = self.get_project_profile(project_id)
        if profile:
            parts.append(f"PROJECT: {profile.get('name', project_id)}")
            if profile.get("domain"):
                parts.append(f"Domain: {profile['domain']}")
            if profile.get("description"):
                parts.append(f"Description: {profile['description']}")

        # Learned patterns
        patterns = self.get_patterns(project_id)
        if patterns.get("common_mistakes"):
            mistakes_str = ", ".join(
                f"{m['type']} ({m['count']}x)" for m in patterns["common_mistakes"][:5]
            )
            parts.append(f"RECURRING MISTAKES IN THIS PROJECT: {mistakes_str}")

        if patterns.get("best_templates"):
            best = patterns["best_templates"][0]
            parts.append(
                f"HIGHEST-SCORING PROMPT IN THIS PROJECT (score {best['score']}):\n\"{best['prompt']}\""
            )

        # Agent-specific context
        if source_agent:
            agent_ctx = self.get_agent_context(project_id, source_agent)
            if agent_ctx.get("total_analyses", 0) > 0:
                parts.append(
                    f"AGENT '{source_agent}' IN THIS PROJECT: "
                    f"avg score={agent_ctx['avg_score']}, "
                    f"analyses={agent_ctx['total_analyses']}"
                )
                if agent_ctx.get("weakest_dimension"):
                    parts.append(
                        f"This agent's weakest dimension: {agent_ctx['weakest_dimension']}"
                    )
                if agent_ctx.get("common_mistakes"):
                    am = ", ".join(
                        m["type"] for m in agent_ctx["common_mistakes"][:3]
                    )
                    parts.append(f"This agent's common mistakes: {am}")

        if not parts:
            return ""

        return (
            "\n\n--- PROJECT CONTEXT (use this to make recommendations more specific) ---\n"
            + "\n".join(parts)
            + "\n--- END PROJECT CONTEXT ---"
        )
