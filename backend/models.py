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
    password: Optional[str] = ""


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


class GoogleLoginRequest(BaseModel):
    credential: str


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
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None


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
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None


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
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    years_of_experience: int = 0
    gender: str = ""
    birth_date: str = ""
    address: str = ""
    achievements: list[str] = Field(default_factory=list)


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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


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


# ============ SQLALCHEMY ORM MODELS ============
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class DBUser(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(String(50), nullable=False)

class DBJobPosting(Base):
    __tablename__ = "job_postings"
    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    department = Column(String(255), default="")
    raw_jd_text = Column(Text, nullable=False)
    file_name = Column(String(255))
    target_position = Column(String(255), default="")
    min_experience_years = Column(Integer, default=0)
    education_requirement = Column(String(255), default="")
    education_level = Column(String(50), default="")
    education_major = Column(String(255), default="")
    responsibilities = Column(JSON)
    criteria = Column(JSON)
    weights = Column(JSON)
    status = Column(String(50), default="draft")
    created_by = Column(String(36), nullable=False)
    created_at = Column(String(50), nullable=False)
    extraction_status = Column(String(50), default="processing")
    extraction_error = Column(Text)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)

class DBCandidate(Base):
    __tablename__ = "candidates"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), default="Unknown")
    email = Column(String(255), default="")
    phone = Column(String(50), default="")
    file_name = Column(String(255), default="")
    raw_text = Column(Text)
    parsed = Column(JSON)
    status = Column(String(50), default="pending")
    error_message = Column(Text)
    created_at = Column(String(50), nullable=False)
    job_posting_id = Column(String(36), nullable=False)
    cv_embedding = Column(JSON, nullable=True)

class DBScreeningResult(Base):
    __tablename__ = "screening_results"
    id = Column(String(36), primary_key=True)
    job_posting_id = Column(String(36), nullable=False)
    candidate_id = Column(String(36), nullable=False)
    total_score = Column(Integer, default=0)
    must_have = Column(JSON)
    experience = Column(JSON)
    domain = Column(JSON)
    education = Column(JSON)
    nice_have = Column(JSON)
    recommendation = Column(String(50), default="review")
    rationale_summary = Column(Text)
    strengths = Column(JSON)
    gaps_summary = Column(JSON)
    decision = Column(String(50), default="pending")
    decided_by = Column(String(36))
    decided_at = Column(String(50))
    created_at = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

class DBAIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    provider_type = Column(String(50), default="emergent")
    base_url = Column(String(255), default="")
    api_key = Column(String(255), default="")
    llm_provider = Column(String(50), default="anthropic")
    model_name = Column(String(50), default="claude-sonnet-4-6")
    temperature = Column(Float, default=0.2)
    max_tokens = Column(Integer, default=4000)
    is_active = Column(Boolean, default=True)
    created_at = Column(String(50), nullable=False)

class DBSystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(String(50), primary_key=True)
    parsing_provider_id = Column(String(36))
    scoring_provider_id = Column(String(36))
    embeddings_provider_id = Column(String(36))


class DBAISearchLog(Base):
    __tablename__ = "ai_search_logs"
    id = Column(String(36), primary_key=True)
    query = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(String(50), nullable=False)


