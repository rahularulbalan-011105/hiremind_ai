from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)


class HrmsAIError(Exception):
    """Base for all typed errors raised by the AI subsystem."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(HrmsAIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationError(HrmsAIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class DependencyError(HrmsAIError):
    """Raised when an external dependency (DB, LLM, model) fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "dependency_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HrmsAIError)
    async def _handle_hrms_error(_: Request, exc: HrmsAIError) -> JSONResponse:
        log.warning("hrms_ai_error", code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def _handle_uncaught(_: Request, exc: Exception) -> JSONResponse:
        log.exception("uncaught_exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "internal_error", "message": str(exc)}},
        )
