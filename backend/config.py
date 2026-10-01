"""
Chunk 1: Configuration Management
---------------------------------
Educational Note for Students:
Centralizing configuration ensures secrets (like API keys) and tuneable parameters
(like concurrency limits and model names) are managed in one predictable place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Locate the root .env file (parent directory or current working directory)
root_dir = Path(__file__).resolve().parent.parent
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
elif (Path(__file__).resolve().parent / ".env").exists():
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
else:
    load_dotenv()

# Groq API configuration
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
HAS_KEY: bool = bool(GROQ_API_KEY)

# Default LLM model: high-speed and cost-effective reasoning
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

# Global concurrency limit: prevents API stampedes and 429 rate limit spikes
LLM_CONCURRENCY: int = int(os.getenv("LLM_CONCURRENCY", "2"))

# Server networking
PORT: int = int(os.getenv("PORT", "8787"))
HOST: str = "0.0.0.0"

# Budget constraints per app build
MAX_LLM_CALLS_PER_BUILD: int = 12
