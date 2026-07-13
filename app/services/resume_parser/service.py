from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DependencyError, ValidationError
from app.core.logging import get_logger
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.parse_jobs import ParseJobRepository
from app.llm import LLMClient, LLMError
from app.llm.prompts import (
    RESUME_PARSER_STRICT_RETRY,
    RESUME_PARSER_SYSTEM,
    RESUME_PARSER_USER_TEMPLATE,
)
from app.schemas.resume_parser import ParsedResume
from app.services.embeddings import EmbeddingService
from app.services.resume_parser.ocr import ocr_pdf
from app.services.resume_parser.text_extract import extract_text, looks_image_based

log = get_logger(__name__)


class ResumeParserService:
    """
    End-to-end orchestrator. Called from the Celery worker.

    Steps:
      1. Read bytes from disk → extract text (PDF/DOCX).
      2. If text is too short, attempt OCR fallback.
      3. Send text to LLM → parse JSON → validate against `ParsedResume`.
         On validation failure, retry once with a stricter prompt.
      4. Persist candidate (+ children) via repository.
      5. Generate + store the resume embedding.
    """

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        embedding_service: EmbeddingService,
    ):
        self.settings = settings
        self.llm = llm
        self.embedding_service = embedding_service

    def parse(self, session: Session, parse_job_id: UUID, file_path: Path,
              bind_candidate_id: UUID | None = None) -> UUID:
        log.info("resume_parse_start", parse_job_id=str(parse_job_id), path=str(file_path),
                 bind_candidate_id=str(bind_candidate_id) if bind_candidate_id else None)
        ParseJobRepository(session).mark(parse_job_id, "running")

        # 1. Text extract
        raw_text = extract_text(file_path)

        # 2. OCR fallback (only for PDFs that came back nearly empty)
        if looks_image_based(raw_text) and file_path.suffix.lower() == ".pdf":
            log.info("ocr_fallback", parse_job_id=str(parse_job_id), engine=self.settings.ocr_engine)
            try:
                raw_text = ocr_pdf(file_path, self.settings.ocr_engine)
            except DependencyError as exc:
                raise ValidationError(
                    f"Resume appears to be image-based and OCR is not available: {exc}"
                ) from exc

        if not raw_text.strip():
            raise ValidationError("No text could be extracted from the resume.")

        # 3. LLM parse + validation (one stricter retry on schema failure)
        parsed = self._call_llm_with_retry(raw_text)

        # 4. Persist. If the structured insert fails but we're binding to an existing
        #    profile (candidate self-service upload), don't lose the résumé embedding —
        #    the candidate row already exists, so we can still store the vector under it.
        candidate_repo = CandidateRepository(session)
        embed_target_id = bind_candidate_id
        try:
            candidate = candidate_repo.create_from_parsed(
                parsed, candidate_id=bind_candidate_id,
                raw_resume_url=f"file://{file_path.as_posix()}", raw_text=raw_text
            )
            embed_target_id = candidate.id
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            session.rollback()
            if bind_candidate_id is None:
                raise  # recruiter-import flow has no existing row to attach the vector to
            log.warning(
                "resume_parse_structured_persist_failed_embedding_only",
                parse_job_id=str(parse_job_id), error=str(exc),
            )

        # 5. Generate + store the résumé embedding (from parsed text) so the AI match's
        #    semantic factor works even when the structured persist above degraded.
        embed_text = self._candidate_embed_text(parsed)
        vector = self.embedding_service.embed(embed_text)
        self.embedding_service.store(session, "resume", embed_target_id, vector)

        log.info(
            "resume_parse_done",
            parse_job_id=str(parse_job_id),
            candidate_id=str(embed_target_id),
            skills=len(parsed.skills),
            experience=len(parsed.experience),
        )
        return embed_target_id

    # ---------- internals ----------

    def _call_llm_with_retry(self, raw_text: str) -> ParsedResume:
        user_prompt = RESUME_PARSER_USER_TEMPLATE.format(resume_text=raw_text)
        try:
            response = self.llm.complete_json(RESUME_PARSER_SYSTEM, user_prompt)
            return _parse_and_validate(response.text)
        except (PydanticValidationError, json.JSONDecodeError, ValueError) as first_err:
            log.warning("resume_llm_validation_failed", error=str(first_err)[:300])
            try:
                response = self.llm.complete_json(
                    RESUME_PARSER_SYSTEM + "\n\n" + RESUME_PARSER_STRICT_RETRY,
                    user_prompt,
                )
                return _parse_and_validate(response.text)
            except (PydanticValidationError, json.JSONDecodeError, ValueError) as second_err:
                raise LLMError(
                    f"LLM returned invalid resume JSON after retry: {second_err}"
                ) from second_err

    @staticmethod
    def _candidate_embed_text(parsed: ParsedResume) -> str:
        parts: list[str] = []
        if parsed.headline:
            parts.append(parsed.headline)
        if parsed.skills:
            parts.append("Skills: " + ", ".join(parsed.skills))
        if parsed.experience:
            parts.append(
                "Experience: "
                + " | ".join(
                    f"{e.title or 'role'} at {e.company}" + (f" — {e.description}" if e.description else "")
                    for e in parsed.experience
                )
            )
        if parsed.education:
            parts.append(
                "Education: "
                + " | ".join(
                    f"{e.degree or 'degree'} {e.field or ''} at {e.institution}".strip()
                    for e in parsed.education
                )
            )
        return "\n".join(parts) or parsed.full_name


def _parse_and_validate(text: str) -> ParsedResume:
    """Tolerant JSON parsing (strip code fences if the LLM ignored instructions)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        # drop leading "json" language tag if present
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    data = json.loads(cleaned)
    return ParsedResume.model_validate(data)
