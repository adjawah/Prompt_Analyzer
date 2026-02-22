import os
from dotenv import load_dotenv

"""Configuration for the Prompt Analyzer."""

# Find the project root (where .env lives)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# LLM parameters
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# Context store
CONTEXT_STORE_DIR = os.getenv(
    "CONTEXT_STORE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "context_store"),
)

# Analytics DB
ANALYTICS_DB_PATH = os.getenv(
    "ANALYTICS_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "analytics.db"),
)
