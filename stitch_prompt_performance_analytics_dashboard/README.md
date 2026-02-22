# Prompt Performance Analytics

A two-agent system for analyzing, scoring, and improving AI prompts — for both humans and enterprise multi-agent systems.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up Anthropic API key
cp .env.example .env
# Edit .env with your Anthropic API key

# 3. Run the server
uvicorn backend.main:app --reload --port 8000

# 4. Open in browser
# Analyzer:  http://localhost:8000/
# Dashboard: http://localhost:8000/dashboard-ui
```

## Architecture

```
Agent 1: Prompt Analyzer ──→ Agent 2: Analytics Reporter ──→ Dashboard
    ↑                              ↑
    ├── REST API (humans)          └── SQLite DB
    └── MCP Server (agents)
```

### Agent 1: Prompt Analyzer
Scores prompts on 5 dimensions (clarity, token efficiency, goal alignment, structure, vagueness), identifies mistakes, and generates optimized rewrites. Uses Anthropic Claude via the official SDK.

### Agent 2: Analytics Reporter
Aggregates all analyses into trends, mistake frequencies, and agent rankings, then serves data to the dashboard.

### Context Store
Per-project isolated memory. Each project's history, patterns, and agent profiles are stored separately — no cross-contamination.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Analyze a prompt |
| POST | `/rewrite-choice` | Record rewrite acceptance |
| GET | `/dashboard/overview` | KPI overview |
| GET | `/dashboard/interactions` | Paginated interaction feed |
| GET | `/dashboard/trends?days=N&hours=N` | Quality score trends |
| GET | `/dashboard/mistakes` | Common mistake types |
| GET | `/dashboard/agents` | Agent leaderboard |

## MCP Server (for agent-to-agent)

```bash
python -m mcp_server.server
```

Tools exposed:
- `analyze_prompt` — analyze a prompt with optional project context
- `get_analysis_history` — retrieve past analyses

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | — |
| `ANTHROPIC_MODEL` | Claude model to use | claude-sonnet-4-20250514 |
| `LLM_MAX_TOKENS` | Max output tokens | 4096 |
| `LLM_TEMPERATURE` | Generation temperature | 0.3 |
