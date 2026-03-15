"""
Google Gemini LLM client.
Uses Gemini 2.0 Flash via langchain-google-genai (free tier).
"""

import os
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.2):
    """
    Return a cached ChatGoogleGenerativeAI instance using Gemini 2.0 Flash.
    Free tier — no billing needed.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set. Add it to your .env file.\n"
            "Get a free key at: https://aistudio.google.com"
        )

    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=temperature,
    )
