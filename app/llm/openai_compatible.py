from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMError, LLMResponse

log = get_logger(__name__)


class OpenAICompatibleClient(LLMClient):
    """
    Shared client for any OpenAI-compatible /chat/completions endpoint.

    Used by both Grok (xAI) and Groq (LPU inference) — they expose the same
    request/response shape. Subclasses (or the factory) configure `backend_name`,
    base URL, key env var, and default model.
    """

    def __init__(
        self,
        *,
        backend_name: str,
        env_var_name: str,
        api_key: str,
        api_base: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        supports_json_mode: bool = True,
    ):
        if not api_key:
            raise LLMError(
                f"{env_var_name} is empty. Set it or switch LLM_BACKEND=mock."
            )
        self.backend_name = backend_name
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout_seconds
        self.supports_json_mode = supports_json_mode
        self._retry_decorator = retry(
            stop=stop_after_attempt(max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
            reraise=True,
        )

    def complete_json(self, system: str, user: str) -> LLMResponse:
        return self._retry_decorator(self._call)(system, user)

    def _call(self, system: str, user: str) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
        }
        if self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        log.info("llm_request", backend=self.backend_name, model=self.model)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.api_base}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.warning(
                "llm_http_error",
                backend=self.backend_name,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.TransportError as exc:
            log.warning("llm_transport_error", backend=self.backend_name, error=str(exc))
            raise

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Unexpected {self.backend_name} response shape: {data}"
            ) from exc

        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=self.model,
            backend=self.backend_name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
