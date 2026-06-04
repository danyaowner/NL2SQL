"""
llm_client.py - Client for OpenRouter API with retry, timeout, error classification.
"""
import os
import time
import logging
from typing import Optional, Tuple
from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError, APIConnectionError
from .config import settings

logger = logging.getLogger("llm")
_client: Optional[OpenAI] = None

def _get_cached_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            timeout=settings.OPENROUTER_TIMEOUT,
            default_headers={
                "HTTP-Referer": "https://github.com/nl2sql",
                "X-Title": "NL2SQL",
            },
        )
    return _client

def generate_sql(prompt, temperature=0.2, model=None, max_retries=2):
    if not settings.OPENROUTER_API_KEY:
        return None, "OPENROUTER_API_KEY not set"
    model_to_use = model or settings.OPENROUTER_MODEL
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            client = _get_cached_client()
            response = client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=settings.OPENROUTER_MAX_TOKENS,
            )
            raw = response.choices[0].message.content.strip() if response.choices else ""
            if not raw:
                last_error = "Empty response"
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None, last_error
            sql = _extract_sql(raw)
            if sql:
                return sql, None
            last_error = "Could not extract SQL"
            if attempt < max_retries:
                continue
            return None, last_error
        except RateLimitError:
            last_error = "Rate limit (429). Try later."
            if attempt < max_retries:
                time.sleep((attempt + 1) * 3)
                continue
        except APITimeoutError:
            last_error = "Request timeout"
            if attempt < max_retries:
                continue
        except APIConnectionError as e:
            last_error = f"Network error: {e}"
            break
        except APIError as e:
            status = getattr(e, "status_code", 0)
            if status == 401:
                last_error = "Invalid API key"
                break
            elif status == 404:
                last_error = f"Model not found: {model_to_use}"
                break
            elif status == 429:
                last_error = "Rate limit (429)"
                if attempt < max_retries:
                    time.sleep(3)
                    continue
            else:
                last_error = f"API error ({status})"
                if attempt < max_retries:
                    time.sleep(2)
                    continue
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            break
    if last_error and model_to_use != settings.OPENROUTER_FALLBACK_MODEL:
        return generate_sql(prompt, temperature, settings.OPENROUTER_FALLBACK_MODEL, 1)
    return None, last_error

def _extract_sql(text):
    """Extract SQL from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Handle ```sql ... ``` blocks
    if "```sql" in text:
        start = text.index("```sql") + 6
        rest = text[start:]
        end = rest.index("```") if "```" in rest else len(rest)
        return rest[:end].strip()
    # Handle ``` ... ``` blocks
    if "```" in text:
        start = text.index("```") + 3
        rest = text[start:]
        end = rest.index("```") if "```" in rest else len(rest)
        return rest[:end].strip()
    # Lines starting with SELECT or WITH
    for line in text.split("\n"):
        s = line.strip().upper()
        if s.startswith("SELECT") or s.startswith("WITH"):
            return line.strip()
    return text
