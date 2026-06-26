"""
Two declarative bases — one per microservice DB.

We deliberately keep separate bases so SQLAlchemy never tries to resolve a
ForeignKey across databases (Postgres can't enforce cross-DB FKs anyway).

  * CandidateBase  → tables in hiremind_candidate
  * CompanyBase    → tables in hiremind_company

Cross-DB references (e.g. match_scores.candidate_id) are stored as bare UUIDs
with no constraint; orphan cleanup is left to a background sweeper.
"""
from sqlalchemy.orm import DeclarativeBase


class CandidateBase(DeclarativeBase):
    """Tables that live in hiremind_candidate."""


class CompanyBase(DeclarativeBase):
    """Tables that live in hiremind_company."""


# Legacy alias kept so older imports don't immediately break. New code should
# import CandidateBase or CompanyBase explicitly.
Base = CandidateBase
