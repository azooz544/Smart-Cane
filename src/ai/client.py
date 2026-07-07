"""
OpenAI client factory for GitHub Models API.

Handles authentication and client initialization.
"""

import openai

from src.config import API_BASE_URL, get_api_key


def build_client() -> openai.OpenAI:
    """
    Create and return an authenticated OpenAI client
    configured for the GitHub Models inference endpoint.
    """
    api_key = get_api_key()
    return openai.OpenAI(
        base_url=API_BASE_URL,
        api_key=api_key,
    )
