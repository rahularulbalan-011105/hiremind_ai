from app.db.models.base import Base, CandidateBase, CompanyBase
from app.db.models.candidate import Candidate
from app.db.models.candidate_children import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,  # deprecated alias; no longer mapped
    CandidatePreference,
    CandidateSkill,
    Skill,
)
from app.db.models.duplicate_job_cluster import DuplicateJobCluster
from app.db.models.embeddings import JobEmbedding, ResumeEmbedding
from app.db.models.fake_profile import FakeProfileScore
from app.db.models.ghost_job_score import GhostJobScore
from app.db.models.hiring_outcome import HiringOutcome
from app.db.models.hiring_prediction import HiringPrediction
from app.db.models.job import (
    Job,
    JobApplication,
    JobBenefit,
    JobEmploymentTypePref,
    JobNoticePeriodPref,
    JobSkill,
)
from app.db.models.match_score import MatchScore
from app.db.models.ml_model import MLModel
from app.db.models.parse_job import ParseJob

__all__ = [
    "Base",
    "CandidateBase",
    "CompanyBase",
    "Candidate",
    "CandidateCertification",
    "CandidateEducation",
    "CandidateExperience",
    "CandidateLanguage",
    "CandidatePreference",
    "CandidateSkill",
    "Skill",
    "DuplicateJobCluster",
    "FakeProfileScore",
    "GhostJobScore",
    "HiringOutcome",
    "HiringPrediction",
    "Job",
    "JobApplication",
    "JobBenefit",
    "JobEmbedding",
    "JobEmploymentTypePref",
    "JobNoticePeriodPref",
    "JobSkill",
    "MatchScore",
    "MLModel",
    "ParseJob",
    "ResumeEmbedding",
]
