"""
Generic AI service for OpenRouter-backed text generation.
"""

import json
import logging
import os
from typing import Any, Dict
from urllib import error, request

try:
    import maricon
except ImportError:
    maricon = None

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-pro")
DEFAULT_SITE_TITLE = "easycore"
REQUEST_TIMEOUT_SECONDS = 60


class AIService:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key and maricon is not None:
            self.api_key = getattr(maricon, "openrouter_api_key", None) or getattr(maricon, "gptkey", None)

        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is required")

        self.model = DEFAULT_MODEL
        self.default_headers = {"X-Title": os.getenv("OPENROUTER_SITE_NAME", DEFAULT_SITE_TITLE)}
        site_url = os.getenv("OPENROUTER_SITE_URL")
        if site_url:
            self.default_headers["HTTP-Referer"] = site_url

    def create_chat_completion(self, messages: list[Dict[str, str]], max_tokens: int = 300) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.default_headers,
        }
        api_request = request.Request(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(api_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter API error {exc.code}: {error_body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"OpenRouter API request failed: {exc.reason}") from exc

        return json.loads(response_body)

    def generate_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 300) -> str:
        response = self.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        logger.info("OpenRouter model %s returned %s choices", self.model, len(response.get("choices", [])))
        return response["choices"][0]["message"]["content"].strip()


ai_service = None


def get_ai_service() -> AIService:
    global ai_service
    if ai_service is None:
        ai_service = AIService()
    return ai_service
