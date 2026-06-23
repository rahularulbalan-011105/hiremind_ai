from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.exceptions import DependencyError


class LLMError(DependencyError):
    """Any LLM call failure (network, timeout, malformed response, etc.)."""

    code = "llm_error"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    backend: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient(ABC):
    """Backend-agnostic LLM interface. All services go through this."""

    backend_name: str
    model: str

    @abstractmethod
    def complete_json(self, system: str, user: str) -> LLMResponse:
        """
        Request a JSON-only completion. The implementation is responsible for
        nudging the backend toward strict JSON (`response_format`, prompt
        instructions, etc.). Caller still validates the returned text against
        a Pydantic schema.
        """
