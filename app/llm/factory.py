from app.core.config import Settings
from app.core.exceptions import DependencyError
from app.llm.base import LLMClient
from app.llm.mock import MockLLMClient
from app.llm.openai_compatible import OpenAICompatibleClient


def get_llm_client(settings: Settings) -> LLMClient:
    backend = settings.llm_backend
    if backend == "mock":
        return MockLLMClient()
    if backend == "grok":
        return OpenAICompatibleClient(
            backend_name="grok",
            env_var_name="GROK_API_KEY",
            api_key=settings.grok_api_key,
            api_base=settings.grok_api_base,
            model=settings.grok_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    if backend == "groq":
        return OpenAICompatibleClient(
            backend_name="groq",
            env_var_name="GROQ_API_KEY",
            api_key=settings.groq_api_key,
            api_base=settings.groq_api_base,
            model=settings.groq_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    raise DependencyError(f"Unknown LLM_BACKEND: {backend}")
