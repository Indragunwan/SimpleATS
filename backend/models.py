"""Pydantic models for CV Screening System."""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ============ USER ============
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str  # hr_recruiter | hiring_manager | admin_it


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: str
    is_active: bool = True
    created_at: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ============ JOB POSTING ============
class JDCriterion(BaseModel):
    id: str = Field(default_factory=_new_id)
    type: str  # must | nice
    category: str  # skill | experience | responsibility | language | certification | custom
    value: str
    weight: int = 3  # 1=ringan, 3=normal, 5=krusial


class ScoringWeights(BaseModel):
    must_have: int = 40
    experience: int = 30
    domain: int = 15
    education: int = 5
    nice_have: int = 10
    # Sub-weights inside the education dimension (must sum to 100)
    edu_level_pct: int = 70  # bobot jenjang (S1/S2/dll)
    edu_major_pct: int = 30  # bobot jurusan
    shortlist_threshold: int = 75
    reject_threshold: int = 40


class JobPostingCreate(BaseModel):
    title: str
    department: Optional[str] = ""
    raw_jd_text: str


class JobPostingUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None  # draft | active | closed | archived
    criteria: Optional[list[JDCriterion]] = None
    weights: Optional[ScoringWeights] = None
    target_position: Optional[str] = None
    min_experience_years: Optional[int] = None
    education_requirement: Optional[str] = None
    education_level: Optional[str] = None
    education_major: Optional[str] = None
    responsibilities: Optional[list[str]] = None


class CriterionInput(BaseModel):
    type: str  # must | nice
    category: str = "skill"
    value: str
    weight: int = 3


class EducationUpdate(BaseModel):
    education_level: Optional[str] = None
    education_major: Optional[str] = None
    edu_level_pct: Optional[int] = None
    edu_major_pct: Optional[int] = None


class JobPosting(BaseModel):
    id: str = Field(default_factory=_new_id)
    title: str
    department: str = ""
    raw_jd_text: str
    file_name: Optional[str] = None
    target_position: str = ""
    min_experience_years: int = 0
    education_requirement: str = ""
    education_level: str = ""
    education_major: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    criteria: list[JDCriterion] = Field(default_factory=list)
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    status: str = "draft"  # draft | active | closed | archived
    created_by: str
    created_at: str = Field(default_factory=_now_iso)


# ============ CANDIDATE ============
class WorkHistoryItem(BaseModel):
    position: str = ""
    company: str = ""
    duration: str = ""
    achievements: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class ParsedCV(BaseModel):
    summary: str = ""
    work_history: list[WorkHistoryItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    years_of_experience: int = 0


class Candidate(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str = "Unknown"
    email: str = ""
    phone: str = ""
    file_name: str = ""
    raw_text: str = ""
    parsed: ParsedCV = Field(default_factory=ParsedCV)
    status: str = "pending"  # pending | processing | parsed | failed
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


# ============ SCREENING ============
class DimensionScore(BaseModel):
    score: int = 0
    explanation: str = ""
    matched_points: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ScreeningResult(BaseModel):
    id: str = Field(default_factory=_new_id)
    job_posting_id: str
    candidate_id: str
    total_score: int = 0
    must_have: DimensionScore = Field(default_factory=DimensionScore)
    experience: DimensionScore = Field(default_factory=DimensionScore)
    domain: DimensionScore = Field(default_factory=DimensionScore)
    education: DimensionScore = Field(default_factory=DimensionScore)
    nice_have: DimensionScore = Field(default_factory=DimensionScore)
    recommendation: str = "review"  # shortlist | review | reject
    rationale_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps_summary: list[str] = Field(default_factory=list)
    decision: str = "pending"  # pending | shortlisted | rejected | hold
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    error_message: Optional[str] = None


class DecisionUpdate(BaseModel):
    decision: str  # shortlisted | rejected | hold | pending


# ============ AI PROVIDER CONFIG ============
class AIProviderConfig(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str = "Emergent Universal (Default)"
    provider_type: str = "emergent"  # emergent | custom
    base_url: str = ""
    api_key: str = ""
    llm_provider: str = "anthropic"  # for emergent: anthropic | openai | gemini
    model_name: str = "claude-sonnet-4-6"
    temperature: float = 0.2
    max_tokens: int = 4000
    is_active: bool = True
    created_at: str = Field(default_factory=_now_iso)


class AIProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None


class TestConnectionRequest(BaseModel):
    provider_type: str = "emergent"
    base_url: str = ""
    api_key: str = ""
    llm_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"
