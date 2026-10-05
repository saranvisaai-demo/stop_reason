"""
Configuration: API client setup, constants, and environment loading.
Supports both Anthropic Console and OpenRouter.ai
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env file
load_dotenv()

# Constants
TEMPERATURE = 1.0  # Default for Claude

# Get API key and provider from environment
API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
PROVIDER = os.getenv("API_PROVIDER", "anthropic").lower()  # "openrouter" or "anthropic"

if not API_KEY:
    raise ValueError(
        "API key not found. "
        "Please set OPENROUTER_API_KEY (for OpenRouter) or ANTHROPIC_API_KEY in .env"
    )

# Set model ID based on provider
# OpenRouter uses different model IDs than Anthropic Console
if PROVIDER == "openrouter":
    MODEL = "anthropic/claude-sonnet-5"  # OpenRouter model format
else:
    MODEL = "claude-sonnet-5-5"  # Anthropic Console model format


def get_client() -> Anthropic:
    """
    Create and return an Anthropic client.

    Supports two providers:
    - Anthropic Console (direct): Uses Anthropic's API servers
    - OpenRouter: Uses OpenRouter.ai proxy with Anthropic SDK
    """
    if PROVIDER == "openrouter":
        # OpenRouter's Anthropic-compatible API. The SDK appends /v1/messages,
        # so the base must stop at /api (not /api/v1).
        return Anthropic(
            api_key=API_KEY,
            base_url="https://openrouter.ai/api"
        )
    else:
        # Default: Anthropic Console
        return Anthropic(api_key=API_KEY)
