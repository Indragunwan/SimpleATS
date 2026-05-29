"""Sistem Penapisan CV Berbasis AI — FastAPI Backend."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update, delete, insert, func, desc, and_, or_, text, case
from models import (
    Base,
    DBUser,
    DBJobPosting,
    DBCandidate,
    DBScreeningResult,
    DBAIProviderConfig,
    DBSystemSettings,
)
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from ai_service import (  # noqa: E402
    calculate_total_score,
    call_llm,
    evaluate_match,
    extract_jd_criteria,
    parse_cv,
    recommendation_from_score,
)
from auth import (  # noqa: E402
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from file_parser import extract_text  # noqa: E402
from models import (  # noqa: E402
    AIProviderUpdate,
    CriterionInput,
    DecisionUpdate,
    EducationUpdate,
    JobPostingCreate,
    JobPostingUpdate,
    LoginRequest,
    LoginResponse,
    TestConnectionRequest,
    UserCreate,
    UserOut,
    UserUpdate,
)
from seed import seed_default_ai_config, seed_demo_users, backfill_criteria_ids  # noqa: E402

# Database Engine setup
DATABASE_URL = os.environ.get("DATABASE_URL", "mysql+aiomysql://root:@localhost/simple_ats")
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Auto create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        await seed_demo_users(session)
        await seed_default_ai_config(session)
        await backfill_criteria_ids(session)
        
    logger.info("Startup complete")
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Sistem Penapisan CV Berbasis AI", lifespan=lifespan)
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cv-screening")


def _clean(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


def _ensure_dict(val) -> dict:
    if not val:
        return {}
    if isinstance(val, str):
        import json
        try:
            return json.loads(val)
        except Exception:
            return {}
    return val


def _ensure_list(val) -> list:
    if not val:
        return []
    if isinstance(val, str):
        import json
        try:
            return json.loads(val)
        except Exception:
            return []
    return val


def _job_to_dict(job: DBJobPosting) -> dict:
    if not job:
        return {}
    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "raw_jd_text": job.raw_jd_text,
        "file_name": job.file_name,
        "target_position": job.target_position,
        "min_experience_years": job.min_experience_years,
        "education_requirement": job.education_requirement,
        "education_level": job.education_level,
        "education_major": job.education_major,
        "responsibilities": _ensure_list(job.responsibilities),
        "criteria": _ensure_list(job.criteria),
        "weights": _ensure_dict(job.weights),
        "status": job.status,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "extraction_status": job.extraction_status,
        "extraction_error": job.extraction_error,
    }


async def _get_active_ai_config(session: AsyncSession) -> dict:
    stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.is_active == True).limit(1)
    res = await session.execute(stmt)
    cfg_obj = res.scalar_one_or_none()
    if not cfg_obj:
        return {
            "provider_type": "emergent",
            "llm_provider": "anthropic",
            "model_name": "claude-sonnet-4-6",
            "temperature": 0.2,
            "max_tokens": 4000,
        }
    return {
        "id": cfg_obj.id,
        "name": cfg_obj.name,
        "provider_type": cfg_obj.provider_type,
        "base_url": cfg_obj.base_url,
        "api_key": cfg_obj.api_key,
        "llm_provider": cfg_obj.llm_provider,
        "model_name": cfg_obj.model_name,
        "temperature": cfg_obj.temperature,
        "max_tokens": cfg_obj.max_tokens,
        "is_active": cfg_obj.is_active,
        "created_at": cfg_obj.created_at,
    }


async def _get_ai_config_for_task(session: AsyncSession, task: str) -> dict:
    """Get AI config for a specific task (parsing | scoring).
    Falls back to the default active provider when no assignment is set.

    Tasks:
      parsing → JD extraction + CV parsing (structural, deterministic)
      scoring → Semantic matching + rationale (judgment, narrative)
    """
    stmt = select(DBSystemSettings).where(DBSystemSettings.id == "task_assignments")
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()
    if settings:
        key = f"{task}_provider_id"
        provider_id = getattr(settings, key, None)
        if provider_id:
            p_stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == provider_id)
            p_res = await session.execute(p_stmt)
            cfg_obj = p_res.scalar_one_or_none()
            if cfg_obj:
                return {
                    "id": cfg_obj.id,
                    "name": cfg_obj.name,
                    "provider_type": cfg_obj.provider_type,
                    "base_url": cfg_obj.base_url,
                    "api_key": cfg_obj.api_key,
                    "llm_provider": cfg_obj.llm_provider,
                    "model_name": cfg_obj.model_name,
                    "temperature": cfg_obj.temperature,
                    "max_tokens": cfg_obj.max_tokens,
                    "is_active": cfg_obj.is_active,
                    "created_at": cfg_obj.created_at,
                }
    return await _get_active_ai_config(session)


# ============ HEALTH ============
@api.get("/health")
async def health(session: AsyncSession = Depends(get_db)) -> dict:
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "ai_provider": bool(os.environ.get("EMERGENT_LLM_KEY")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============ AUTH ============
@api.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> LoginResponse:
    stmt = select(DBUser).where(DBUser.email == payload.email.lower())
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    token = create_access_token(user.id, user.role, user.email)
    return LoginResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=getattr(user, "is_active", True),
            created_at=user.created_at,
        ),
    )


@api.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> UserOut:
    stmt = select(DBUser).where(DBUser.id == user["id"])
    res = await session.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return UserOut(
        id=doc.id,
        name=doc.name,
        email=doc.email,
        role=doc.role,
        is_active=doc.is_active,
        created_at=doc.created_at,
    )


# ============ USER MANAGEMENT (Admin) ============
@api.get("/users", response_model=list[UserOut])
async def list_users(
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    stmt = select(DBUser)
    res = await session.execute(stmt)
    users = res.scalars().all()
    return [
        UserOut(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@api.post("/users", response_model=UserOut)
async def create_user(
    payload: UserCreate,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    if payload.role not in ("hr_recruiter", "hiring_manager", "admin_it"):
        raise HTTPException(400, "Role tidak valid")
    stmt = select(DBUser).where(DBUser.email == payload.email.lower())
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Email sudah terdaftar")
    import uuid

    db_user = DBUser(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(db_user)
    await session.commit()
    return UserOut(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        role=db_user.role,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
    )


@api.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    stmt = select(DBUser).where(DBUser.id == user_id)
    res = await session.execute(stmt)
    db_user = res.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User tidak ditemukan")
    has_changes = False
    if payload.name is not None:
        db_user.name = payload.name
        has_changes = True
    if payload.role is not None:
        if payload.role not in ("hr_recruiter", "hiring_manager", "admin_it"):
            raise HTTPException(400, "Role tidak valid")
        db_user.role = payload.role
        has_changes = True
    if payload.is_active is not None:
        db_user.is_active = payload.is_active
        has_changes = True
    if payload.password:
        db_user.password_hash = hash_password(payload.password)
        has_changes = True
    if not has_changes:
        raise HTTPException(400, "Tidak ada perubahan")
    await session.commit()
    return UserOut(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        role=db_user.role,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
    )


# ============ JOB POSTINGS ============
@api.post("/jobs")
async def create_job(
    title: str = Form(...),
    raw_jd_text: str = Form(""),
    raw_spec_text: str = Form(""),
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    import uuid

    jd = raw_jd_text.strip()
    spec = raw_spec_text.strip()
    text = ""
    if jd:
        text += "Teks JD / Tanggung Jawab:\n" + jd + "\n\n"
    if spec:
        text += "Teks Spesifikasi / Kualifikasi:\n" + spec + "\n\n"

    if (len(jd) + len(spec)) < 10:
        raise HTTPException(400, "Teks JD atau Spesifikasi terlalu pendek atau kosong")

    job_id = str(uuid.uuid4())
    weights = {
        "must_have": 40,
        "experience": 30,
        "domain": 15,
        "education": 5,
        "nice_have": 10,
        "edu_level_pct": 70,
        "edu_major_pct": 30,
        "shortlist_threshold": 75,
        "reject_threshold": 40,
    }
    db_job = DBJobPosting(
        id=job_id,
        title=title,
        department="",
        raw_jd_text=text,
        file_name=None,
        target_position="",
        min_experience_years=0,
        education_requirement="",
        education_level="",
        education_major="",
        responsibilities=[],
        criteria=[],
        weights=weights,
        status="draft",
        created_by=user["id"],
        created_at=datetime.now(timezone.utc).isoformat(),
        extraction_status="processing",
        extraction_error=None,
    )
    session.add(db_job)
    await session.commit()

    # Trigger extraction (sync but fast - LLM call ~5-15s)
    try:
        cfg = await _get_ai_config_for_task(session, "parsing")
        extracted = await extract_jd_criteria(text, cfg)
        import uuid as _u

        criteria = []
        for v in extracted.get("must_have", []):
            criteria.append({"id": str(_u.uuid4()), "type": "must", "category": "skill", "value": v, "weight": 3})
        for v in extracted.get("nice_to_have", []):
            criteria.append({"id": str(_u.uuid4()), "type": "nice", "category": "skill", "value": v, "weight": 3})
        
        db_job.target_position = extracted.get("target_position", "")
        db_job.min_experience_years = extracted.get("min_experience_years", 0)
        db_job.education_requirement = extracted.get("education_requirement", "")
        db_job.education_level = extracted.get("education_level", "")
        db_job.education_major = extracted.get("education_major", "")
        db_job.responsibilities = extracted.get("responsibilities", [])
        db_job.criteria = criteria
        db_job.extraction_status = "done"
        db_job.status = "active"
        await session.commit()
    except Exception as e:
        logger.exception("JD extraction failed")
        db_job.extraction_status = "failed"
        db_job.extraction_error = str(e)
        await session.commit()

    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    refreshed_job = res.scalar_one_or_none()
    return _job_to_dict(refreshed_job)


@api.get("/jobs")
async def list_jobs(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(DBJobPosting).order_by(desc(DBJobPosting.created_at))
    res = await session.execute(stmt)
    jobs = res.scalars().all()
    
    out = []
    for job in jobs:
        d = _job_to_dict(job)
        count_stmt = select(func.count()).select_from(DBScreeningResult).where(DBScreeningResult.job_posting_id == job.id)
        count_res = await session.execute(count_stmt)
        d["candidate_count"] = count_res.scalar() or 0
        out.append(d)
    return out


@api.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    return _job_to_dict(job)


@api.patch("/jobs/{job_id}")
async def update_job(
    job_id: str,
    payload: JobPostingUpdate,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(400, "Tidak ada perubahan")
    for k, v in update_data.items():
        setattr(job, k, v)
    from sqlalchemy.orm.attributes import flag_modified
    if "criteria" in update_data:
        flag_modified(job, "criteria")
    if "weights" in update_data:
        flag_modified(job, "weights")
    if "responsibilities" in update_data:
        flag_modified(job, "responsibilities")
    await session.commit()
    return _job_to_dict(job)


@api.post("/jobs/{job_id}/reextract")
async def reextract_job(
    job_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    cfg = await _get_ai_config_for_task(session, "parsing")
    extracted = await extract_jd_criteria(job.raw_jd_text, cfg)
    import uuid as _u

    criteria = []
    for v in extracted.get("must_have", []):
        criteria.append({"id": str(_u.uuid4()), "type": "must", "category": "skill", "value": v, "weight": 3})
    for v in extracted.get("nice_to_have", []):
        criteria.append({"id": str(_u.uuid4()), "type": "nice", "category": "skill", "value": v, "weight": 3})
    job.target_position = extracted.get("target_position", "")
    job.min_experience_years = extracted.get("min_experience_years", 0)
    job.education_requirement = extracted.get("education_requirement", "")
    job.education_level = extracted.get("education_level", "")
    job.education_major = extracted.get("education_major", "")
    job.responsibilities = extracted.get("responsibilities", [])
    job.criteria = criteria
    job.extraction_status = "done"
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "criteria")
    flag_modified(job, "responsibilities")
    await session.commit()
    return _job_to_dict(job)


# ============ JD CRITERIA CRUD ============
@api.post("/jobs/{job_id}/criteria")
async def add_criterion(
    job_id: str,
    payload: CriterionInput,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if payload.type not in ("must", "nice"):
        raise HTTPException(400, "Tipe harus 'must' atau 'nice'")
    if not (1 <= payload.weight <= 5):
        raise HTTPException(400, "Bobot harus 1-5")
    if not payload.value.strip():
        raise HTTPException(400, "Nilai kriteria tidak boleh kosong")
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    import uuid as _u

    item = {
        "id": str(_u.uuid4()),
        "type": payload.type,
        "category": payload.category or "skill",
        "value": payload.value.strip(),
        "weight": payload.weight,
    }
    criteria = list(job.criteria or [])
    criteria.append(item)
    job.criteria = criteria
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "criteria")
    await session.commit()
    return item


@api.patch("/jobs/{job_id}/criteria/{criterion_id}")
async def update_criterion(
    job_id: str,
    criterion_id: str,
    payload: CriterionInput,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if payload.type not in ("must", "nice"):
        raise HTTPException(400, "Tipe harus 'must' atau 'nice'")
    if not (1 <= payload.weight <= 5):
        raise HTTPException(400, "Bobot harus 1-5")
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    criteria = list(job.criteria or [])
    found = False
    for c in criteria:
        if c.get("id") == criterion_id:
            c["type"] = payload.type
            c["category"] = payload.category or "skill"
            c["value"] = payload.value.strip()
            c["weight"] = payload.weight
            found = True
            break
    if not found:
        raise HTTPException(404, "Kriteria tidak ditemukan")
    job.criteria = criteria
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "criteria")
    await session.commit()
    return {"status": "updated"}


@api.delete("/jobs/{job_id}/criteria/{criterion_id}")
async def delete_criterion(
    job_id: str,
    criterion_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    criteria = list(job.criteria or [])
    original_len = len(criteria)
    criteria = [c for c in criteria if c.get("id") != criterion_id]
    if len(criteria) == original_len:
        raise HTTPException(404, "Kriteria tidak ditemukan")
    job.criteria = criteria
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "criteria")
    await session.commit()
    return {"status": "deleted"}


@api.patch("/jobs/{job_id}/education")
async def update_education(
    job_id: str,
    payload: EducationUpdate,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    weights = dict(job.weights or {})
    weights_changed = False
    if payload.edu_level_pct is not None or payload.edu_major_pct is not None:
        lvl = payload.edu_level_pct if payload.edu_level_pct is not None else weights.get("edu_level_pct", 70)
        maj = payload.edu_major_pct if payload.edu_major_pct is not None else weights.get("edu_major_pct", 30)
        if lvl < 0 or maj < 0 or (lvl + maj) != 100:
            raise HTTPException(400, "Bobot jenjang + jurusan harus berjumlah 100")
        weights["edu_level_pct"] = lvl
        weights["edu_major_pct"] = maj
        weights_changed = True
    if payload.education_level is not None:
        job.education_level = payload.education_level.strip()
    if payload.education_major is not None:
        job.education_major = payload.education_major.strip()
    lvl = job.education_level
    maj = job.education_major
    job.education_requirement = (
        f"{lvl} - {maj}" if lvl and maj and maj.lower() not in ("semua jurusan", "") else (lvl or maj or "")
    )
    if weights_changed:
        job.weights = weights
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(job, "weights")
    await session.commit()
    return _job_to_dict(job)


# ============ CANDIDATES + SCREENING ============
async def _screen_candidate_for_job(
    session: AsyncSession, candidate_id: str, job_id: str, parsed: dict, cfg: Optional[dict] = None
) -> Optional[str]:
    """Run semantic matching for one candidate against one job and persist result."""
    import uuid

    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        return None
    if cfg is None:
        cfg = await _get_ai_config_for_task(session, "scoring")
    weights = job.weights or {}
    jd_data = {
        "target_position": job.target_position or "",
        "department": job.department or "",
        "min_experience_years": job.min_experience_years or 0,
        "education_requirement": job.education_requirement or "",
        "education_level": job.education_level or "",
        "education_major": job.education_major or "",
        "edu_level_pct": weights.get("edu_level_pct", 70),
        "edu_major_pct": weights.get("edu_major_pct", 30),
        "responsibilities": job.responsibilities or [],
        "must_have": [
            {"value": c["value"], "weight": c.get("weight", 3)}
            for c in (job.criteria or []) if c.get("type") == "must"
        ],
        "nice_to_have": [
            {"value": c["value"], "weight": c.get("weight", 3)}
            for c in (job.criteria or []) if c.get("type") == "nice"
        ],
    }
    evaluation = await evaluate_match(jd_data, parsed, cfg)
    total = calculate_total_score(evaluation, weights)
    recommendation = recommendation_from_score(total, weights)

    sr_id = str(uuid.uuid4())
    sr = DBScreeningResult(
        id=sr_id,
        job_posting_id=job_id,
        candidate_id=candidate_id,
        total_score=total,
        must_have=evaluation["must_have"],
        experience=evaluation["experience"],
        domain=evaluation["domain"],
        education=evaluation["education"],
        nice_have=evaluation["nice_have"],
        recommendation=recommendation,
        rationale_summary=evaluation["rationale_summary"],
        strengths=evaluation["strengths"],
        gaps_summary=evaluation["gaps_summary"],
        decision="pending",
        decided_by=None,
        decided_at=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(sr)
    await session.commit()
    return sr_id


async def _process_candidate(candidate_id: str, job_id: str) -> None:
    """Background task: parse CV + evaluate against JD."""
    try:
        async with async_session() as session:
            stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
            res = await session.execute(stmt)
            cand = res.scalar_one_or_none()
            if not cand:
                return
            parsing_cfg = await _get_ai_config_for_task(session, "parsing")
            scoring_cfg = await _get_ai_config_for_task(session, "scoring")
            cand.status = "processing"
            await session.commit()
            
            parsed = await parse_cv(cand.raw_text, parsing_cfg)
            cand.name = parsed.get("name") or cand.name or "Unknown"
            cand.email = parsed.get("email", "")
            cand.phone = parsed.get("phone", "")
            cand.parsed = parsed
            cand.status = "parsed"
            await session.commit()
            
            await _screen_candidate_for_job(session, candidate_id, job_id, parsed, scoring_cfg)
    except Exception as e:
        logger.exception("Candidate processing failed")
        async with async_session() as session:
            stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
            res = await session.execute(stmt)
            cand = res.scalar_one_or_none()
            if cand:
                cand.status = "failed"
                cand.error_message = str(e)
                await session.commit()


async def _rescreen_pool_candidate(candidate_id: str, job_id: str) -> None:
    """Background task: rescreen an already-parsed candidate against another job."""
    try:
        async with async_session() as session:
            stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
            res = await session.execute(stmt)
            cand = res.scalar_one_or_none()
            if not cand or cand.status != "parsed":
                return
            exists_stmt = select(DBScreeningResult).where(
                and_(
                    DBScreeningResult.candidate_id == candidate_id,
                    DBScreeningResult.job_posting_id == job_id
                )
            )
            exists_res = await session.execute(exists_stmt)
            exists = exists_res.scalar_one_or_none()
            if exists:
                return
            scoring_cfg = await _get_ai_config_for_task(session, "scoring")
            await _screen_candidate_for_job(session, candidate_id, job_id, cand.parsed or {}, scoring_cfg)
    except Exception:
        logger.exception("Rescreen failed for candidate %s", candidate_id)


@api.post("/jobs/{job_id}/upload-cv")
async def upload_cv(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if len(files) > 500:
        raise HTTPException(400, "Maksimum 500 CV per sesi")
    import uuid

    created_ids: list[str] = []
    for f in files:
        content = await f.read()
        text = extract_text(f.filename or "cv.txt", content)
        import re
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text).strip()
        cid = str(uuid.uuid4())
        doc = DBCandidate(
            id=cid,
            name="Memproses...",
            email="",
            phone="",
            file_name=f.filename,
            raw_text=text,
            parsed={},
            status="pending",
            error_message=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            job_posting_id=job_id,
        )
        session.add(doc)
        created_ids.append(cid)
    await session.commit()
    for cid in created_ids:
        background_tasks.add_task(_process_candidate, cid, job_id)
    return {"uploaded": len(created_ids), "candidate_ids": created_ids}


@api.get("/jobs/{job_id}/candidates")
async def list_job_candidates(
    job_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return ranked list of screening results joined with candidate info."""
    stmt_sr = select(DBScreeningResult).where(DBScreeningResult.job_posting_id == job_id)
    res_sr = await session.execute(stmt_sr)
    results = res_sr.scalars().all()
    stmt_c = select(DBCandidate).where(DBCandidate.job_posting_id == job_id)
    res_c = await session.execute(stmt_c)
    candidates = res_c.scalars().all()
    cand_map = {
        c.id: {
            "name": c.name,
            "email": c.email,
            "status": c.status,
            "created_at": c.created_at,
        }
        for c in candidates
    }
    scored_ids = {r.candidate_id for r in results}

    out = []
    for r in results:
        c = cand_map.get(r.candidate_id, {})
        out.append(
            {
                "id": r.id,
                "job_posting_id": r.job_posting_id,
                "candidate_id": r.candidate_id,
                "total_score": r.total_score,
                "must_have": r.must_have,
                "experience": r.experience,
                "domain": r.domain,
                "education": r.education,
                "nice_have": r.nice_have,
                "recommendation": r.recommendation,
                "rationale_summary": r.rationale_summary,
                "strengths": r.strengths,
                "gaps_summary": r.gaps_summary,
                "decision": r.decision,
                "decided_by": r.decided_by,
                "decided_at": r.decided_at,
                "created_at": r.created_at,
                "candidate_name": c.get("name", "Unknown"),
                "candidate_email": c.get("email", ""),
                "candidate_status": c.get("status", "parsed"),
            }
        )
    out.sort(key=lambda x: x["total_score"], reverse=True)

    for c in candidates:
        if c.id not in scored_ids:
            out.append(
                {
                    "id": None,
                    "job_posting_id": job_id,
                    "candidate_id": c.id,
                    "candidate_name": c.name or "Memproses...",
                    "candidate_email": c.email or "",
                    "candidate_status": c.status or "pending",
                    "total_score": 0,
                    "recommendation": "pending",
                    "decision": "pending",
                    "rationale_summary": "",
                    "created_at": c.created_at,
                }
            )
    return out


@api.delete("/jobs/{job_id}/candidates/{candidate_id}")
async def delete_candidate(
    job_id: str,
    candidate_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt_sr = select(DBScreeningResult).where(DBScreeningResult.candidate_id == candidate_id)
    res_sr = await session.execute(stmt_sr)
    for sr in res_sr.scalars().all():
        await session.delete(sr)

    stmt_c = select(DBCandidate).where(DBCandidate.id == candidate_id)
    res_c = await session.execute(stmt_c)
    cand = res_c.scalar_one_or_none()
    if cand:
        await session.delete(cand)

    await session.commit()
    return {"status": "ok"}


@api.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import func
    stmt_c = select(DBCandidate).where(DBCandidate.job_posting_id == job_id)
    res_c = await session.execute(stmt_c)
    candidates = res_c.scalars().all()
    for c in candidates:
        await session.delete(c)

    # Cleanup potential orphan screening results
    stmt_sr = select(DBScreeningResult).where(DBScreeningResult.job_posting_id == job_id)
    res_sr = await session.execute(stmt_sr)
    for sr in res_sr.scalars().all():
        await session.delete(sr)

    stmt_j = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res_j = await session.execute(stmt_j)
    job = res_j.scalar_one_or_none()
    if job:
        await session.delete(job)

    await session.commit()
    return {"status": "ok"}


@api.get("/screenings/{screening_id}")
async def get_screening(
    screening_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt_sr = select(DBScreeningResult).where(DBScreeningResult.id == screening_id)
    res_sr = await session.execute(stmt_sr)
    sr = res_sr.scalar_one_or_none()
    if not sr:
        raise HTTPException(404, "Hasil screening tidak ditemukan")
    stmt_c = select(DBCandidate).where(DBCandidate.id == sr.candidate_id)
    res_c = await session.execute(stmt_c)
    cand = res_c.scalar_one_or_none()
    stmt_job = select(DBJobPosting).where(DBJobPosting.id == sr.job_posting_id)
    res_job = await session.execute(stmt_job)
    job = res_job.scalar_one_or_none()
    sr_dict = {
        "id": sr.id,
        "job_posting_id": sr.job_posting_id,
        "candidate_id": sr.candidate_id,
        "total_score": sr.total_score,
        "must_have": sr.must_have,
        "experience": sr.experience,
        "domain": sr.domain,
        "education": sr.education,
        "nice_have": sr.nice_have,
        "recommendation": sr.recommendation,
        "rationale_summary": sr.rationale_summary,
        "strengths": sr.strengths,
        "gaps_summary": sr.gaps_summary,
        "decision": sr.decision,
        "decided_by": sr.decided_by,
        "decided_at": sr.decided_at,
        "created_at": sr.created_at,
    }
    cand_dict = {
        "id": cand.id,
        "name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "file_name": cand.file_name,
        "parsed": cand.parsed,
        "status": cand.status,
        "error_message": cand.error_message,
        "created_at": cand.created_at,
        "job_posting_id": cand.job_posting_id,
    } if cand else None
    job_dict = _job_to_dict(job) if job else None
    return {"screening": sr_dict, "candidate": cand_dict, "job": job_dict}


# ============ TALENT POOL ============
@api.get("/talent-pool")
async def list_talent_pool(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return all parsed candidates with their best score across all jobs."""
    stmt_c = select(DBCandidate).where(DBCandidate.status == "parsed")
    res_c = await session.execute(stmt_c)
    candidates = res_c.scalars().all()
    stmt_stats = select(
        DBScreeningResult.candidate_id,
        func.max(DBScreeningResult.total_score).label("best_score"),
        func.count(DBScreeningResult.id).label("screenings_count"),
        func.sum(
            case(
                (DBScreeningResult.decision == "shortlisted", 1),
                else_=0
            )
        ).label("shortlisted_count")
    ).group_by(DBScreeningResult.candidate_id)
    res_stats = await session.execute(stmt_stats)
    stats_rows = res_stats.all()
    stats = {}
    for row in stats_rows:
        stats[row.candidate_id] = {
            "best_score": row.best_score or 0,
            "screenings_count": row.screenings_count or 0,
            "shortlisted_count": int(row.shortlisted_count or 0),
        }
    out = []
    for c in candidates:
        s = stats.get(c.id, {})
        parsed = _ensure_dict(c.parsed)
        work_history = parsed.get("work_history", [])
        current_position = ""
        if work_history and isinstance(work_history, list) and len(work_history) > 0:
            if isinstance(work_history[0], dict):
                current_position = work_history[0].get("position", "")
        out.append(
            {
                "id": c.id,
                "name": c.name or "Unknown",
                "email": c.email or "",
                "phone": c.phone or "",
                "years_of_experience": parsed.get("years_of_experience", 0),
                "top_skills": (parsed.get("skills", []) or [])[:6],
                "current_position": current_position,
                "best_score": s.get("best_score", 0),
                "screenings_count": s.get("screenings_count", 0),
                "shortlisted_count": s.get("shortlisted_count", 0),
                "created_at": c.created_at,
            }
        )
    out.sort(key=lambda x: (x["best_score"], x["screenings_count"]), reverse=True)
    return out


@api.get("/talent-pool/{candidate_id}")
async def get_pool_candidate(
    candidate_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get candidate detail + all screenings across jobs."""
    stmt_c = select(DBCandidate).where(DBCandidate.id == candidate_id)
    res_c = await session.execute(stmt_c)
    cand = res_c.scalar_one_or_none()
    if not cand:
        raise HTTPException(404, "Kandidat tidak ditemukan")
    stmt_sr = select(DBScreeningResult).where(DBScreeningResult.candidate_id == candidate_id).order_by(desc(DBScreeningResult.created_at))
    res_sr = await session.execute(stmt_sr)
    screenings = res_sr.scalars().all()
    job_ids = list({s.job_posting_id for s in screenings})
    job_map = {}
    if job_ids:
        stmt_job = select(DBJobPosting).where(DBJobPosting.id.in_(job_ids))
        res_job = await session.execute(stmt_job)
        jobs = res_job.scalars().all()
        job_map = {j.id: j for j in jobs}
    screenings_out = []
    for s in screenings:
        j = job_map.get(s.job_posting_id)
        screenings_out.append({
            "id": s.id,
            "job_posting_id": s.job_posting_id,
            "candidate_id": s.candidate_id,
            "total_score": s.total_score,
            "must_have": s.must_have,
            "experience": s.experience,
            "domain": s.domain,
            "education": s.education,
            "nice_have": s.nice_have,
            "recommendation": s.recommendation,
            "rationale_summary": s.rationale_summary,
            "strengths": s.strengths,
            "gaps_summary": s.gaps_summary,
            "decision": s.decision,
            "decided_by": s.decided_by,
            "decided_at": s.decided_at,
            "created_at": s.created_at,
            "job_title": j.title if j else "—",
            "job_department": j.department if j else "",
        })
    cand_dict = {
        "id": cand.id,
        "name": cand.name,
        "email": cand.email,
        "phone": cand.phone,
        "file_name": cand.file_name,
        "parsed": cand.parsed,
        "status": cand.status,
        "error_message": cand.error_message,
        "created_at": cand.created_at,
        "job_posting_id": cand.job_posting_id,
    }
    return {"candidate": cand_dict, "screenings": screenings_out}


class ScreenFromPoolRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    auto_top_n: int = 0  # if > 0, ignore candidate_ids and pick top-N from pool not yet screened


@api.post("/jobs/{job_id}/screen-from-pool")
async def screen_from_pool(
    job_id: str,
    payload: ScreenFromPoolRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt_job = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res_job = await session.execute(stmt_job)
    job = res_job.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    stmt_already = select(DBScreeningResult.candidate_id).where(DBScreeningResult.job_posting_id == job_id)
    res_already = await session.execute(stmt_already)
    already = set(res_already.scalars().all())

    if payload.auto_top_n and payload.auto_top_n > 0:
        stmt_agg = select(
            DBScreeningResult.candidate_id,
            func.max(DBScreeningResult.total_score).label("best_score")
        ).group_by(DBScreeningResult.candidate_id).order_by(desc("best_score"))
        res_agg = await session.execute(stmt_agg)
        agg = res_agg.all()
        top_ids = [row.candidate_id for row in agg if row.candidate_id not in already][:payload.auto_top_n]
        if len(top_ids) < payload.auto_top_n:
            exclude_ids = list(already) + top_ids
            stmt_extra = select(DBCandidate.id).where(
                and_(
                    DBCandidate.status == "parsed",
                    DBCandidate.id.notin_(exclude_ids) if exclude_ids else True
                )
            ).limit(payload.auto_top_n - len(top_ids))
            res_extra = await session.execute(stmt_extra)
            extra = res_extra.scalars().all()
            top_ids.extend(extra)
        target_ids = top_ids
    else:
        target_ids = [cid for cid in payload.candidate_ids if cid not in already]

    queued = 0
    for cid in target_ids:
        stmt_cand = select(DBCandidate).where(DBCandidate.id == cid)
        res_cand = await session.execute(stmt_cand)
        cand = res_cand.scalar_one_or_none()
        if not cand or cand.status != "parsed":
            continue
        background_tasks.add_task(_rescreen_pool_candidate, cid, job_id)
        queued += 1
    return {
        "queued": queued,
        "skipped_already_screened": len(payload.candidate_ids) - queued
        if not payload.auto_top_n
        else 0,
    }


@api.patch("/screenings/{screening_id}/decision")
async def update_decision(
    screening_id: str,
    payload: DecisionUpdate,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if payload.decision not in ("shortlisted", "rejected", "hold", "pending"):
        raise HTTPException(400, "Keputusan tidak valid")
    stmt = select(DBScreeningResult).where(DBScreeningResult.id == screening_id)
    res = await session.execute(stmt)
    sr = res.scalar_one_or_none()
    if not sr:
        raise HTTPException(404, "Hasil screening tidak ditemukan")
    sr.decision = payload.decision
    sr.decided_by = user["id"]
    sr.decided_at = datetime.now(timezone.utc).isoformat()
    await session.commit()
    return {
        "id": sr.id,
        "job_posting_id": sr.job_posting_id,
        "candidate_id": sr.candidate_id,
        "total_score": sr.total_score,
        "must_have": sr.must_have,
        "experience": sr.experience,
        "domain": sr.domain,
        "education": sr.education,
        "nice_have": sr.nice_have,
        "recommendation": sr.recommendation,
        "rationale_summary": sr.rationale_summary,
        "strengths": sr.strengths,
        "gaps_summary": sr.gaps_summary,
        "decision": sr.decision,
        "decided_by": sr.decided_by,
        "decided_at": sr.decided_at,
        "created_at": sr.created_at,
    }


# ============ AI PROVIDER CONFIG ============
@api.get("/config/ai-providers")
async def list_providers(
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(DBAIProviderConfig)
    res = await session.execute(stmt)
    configs = res.scalars().all()
    out = []
    for c in configs:
        api_key_masked = ""
        if c.api_key:
            api_key_masked = "***" + c.api_key[-4:] if len(c.api_key) > 4 else "***"
        out.append({
            "id": c.id,
            "name": c.name,
            "provider_type": c.provider_type,
            "base_url": c.base_url,
            "api_key": api_key_masked,
            "llm_provider": c.llm_provider,
            "model_name": c.model_name,
            "temperature": c.temperature,
            "max_tokens": c.max_tokens,
            "is_active": c.is_active,
            "created_at": c.created_at,
        })
    return out


@api.patch("/config/ai-providers/{cfg_id}")
async def update_provider(
    cfg_id: str,
    payload: AIProviderUpdate,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == cfg_id)
    res = await session.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Konfigurasi tidak ditemukan")
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("is_active"):
        deact_stmt = update(DBAIProviderConfig).where(DBAIProviderConfig.id != cfg_id).values(is_active=False)
        await session.execute(deact_stmt)
    for k, v in update_data.items():
        setattr(cfg, k, v)
    await session.commit()
    api_key_masked = ""
    if cfg.api_key:
        api_key_masked = "***" + cfg.api_key[-4:] if len(cfg.api_key) > 4 else "***"
    return {
        "id": cfg.id,
        "name": cfg.name,
        "provider_type": cfg.provider_type,
        "base_url": cfg.base_url,
        "api_key": api_key_masked,
        "llm_provider": cfg.llm_provider,
        "model_name": cfg.model_name,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "is_active": cfg.is_active,
        "created_at": cfg.created_at,
    }


@api.post("/config/ai-providers")
async def create_provider(
    payload: AIProviderUpdate,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    import uuid

    cfg_id = str(uuid.uuid4())
    doc = DBAIProviderConfig(
        id=cfg_id,
        name=payload.name or "Custom Provider",
        provider_type=payload.provider_type or "custom",
        base_url=payload.base_url or "",
        api_key=payload.api_key or "",
        llm_provider=payload.llm_provider or "openai",
        model_name=payload.model_name or "gpt-4o-mini",
        temperature=payload.temperature if payload.temperature is not None else 0.2,
        max_tokens=payload.max_tokens or 4000,
        is_active=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(doc)
    await session.commit()
    api_key_masked = ""
    if doc.api_key:
        api_key_masked = "***" + doc.api_key[-4:] if len(doc.api_key) > 4 else "***"
    return {
        "id": doc.id,
        "name": doc.name,
        "provider_type": doc.provider_type,
        "base_url": doc.base_url,
        "api_key": api_key_masked,
        "llm_provider": doc.llm_provider,
        "model_name": doc.model_name,
        "temperature": doc.temperature,
        "max_tokens": doc.max_tokens,
        "is_active": doc.is_active,
        "created_at": doc.created_at,
    }


@api.delete("/config/ai-providers/{cfg_id}")
async def delete_provider(
    cfg_id: str,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == cfg_id)
    res = await session.execute(stmt)
    provider = res.scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Konfigurasi tidak ditemukan")
    if provider.is_active:
        raise HTTPException(400, "Tidak bisa menghapus provider yang sedang aktif")
    stmt_settings = select(DBSystemSettings).where(DBSystemSettings.id == "task_assignments")
    res_settings = await session.execute(stmt_settings)
    settings = res_settings.scalar_one_or_none()
    if settings:
        if settings.parsing_provider_id == cfg_id or settings.scoring_provider_id == cfg_id:
            raise HTTPException(400, "Tidak bisa menghapus provider yang sedang digunakan pada penugasan model")
    await session.delete(provider)
    await session.commit()
    return {"status": "deleted"}


@api.post("/config/ai-providers/test")
async def test_provider(
    payload: TestConnectionRequest, user: dict = Depends(require_roles("admin_it"))
) -> dict:
    try:
        cfg = payload.model_dump()
        result = await asyncio.wait_for(
            call_llm(
                "You are a connectivity test. Respond with the exact text: OK",
                "Reply OK only.",
                cfg,
            ),
            timeout=30,
        )
        return {"success": True, "response": result[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@api.post("/config/ai-providers/{cfg_id}/test")
async def test_existing_provider(
    cfg_id: str,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == cfg_id)
    res = await session.execute(stmt)
    cfg_obj = res.scalar_one_or_none()
    if not cfg_obj:
        raise HTTPException(404, "Konfigurasi tidak ditemukan")
    try:
        cfg = {
            "provider_type": cfg_obj.provider_type,
            "base_url": cfg_obj.base_url or "",
            "api_key": cfg_obj.api_key or "",
            "llm_provider": cfg_obj.llm_provider,
            "model_name": cfg_obj.model_name,
        }
        result = await asyncio.wait_for(
            call_llm(
                "You are a connectivity test. Respond with the exact text: OK",
                "Reply OK only.",
                cfg,
            ),
            timeout=30,
        )
        return {"success": True, "response": result[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}



# ============ TASK MODEL ASSIGNMENTS ============
class TaskAssignmentUpdate(BaseModel):
    parsing_provider_id: Optional[str] = None
    scoring_provider_id: Optional[str] = None


@api.get("/config/task-assignments")
async def get_task_assignments(
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBSystemSettings).where(DBSystemSettings.id == "task_assignments")
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()
    parsing_id = settings.parsing_provider_id if settings else None
    scoring_id = settings.scoring_provider_id if settings else None

    async def _resolve(pid: Optional[str]) -> Optional[dict]:
        if not pid:
            return None
        p_stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == pid)
        p_res = await session.execute(p_stmt)
        p = p_res.scalar_one_or_none()
        if not p:
            return None
        api_key_masked = ""
        if p.api_key:
            api_key_masked = "***" + p.api_key[-4:] if len(p.api_key) > 4 else "***"
        return {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "base_url": p.base_url,
            "api_key": api_key_masked,
            "llm_provider": p.llm_provider,
            "model_name": p.model_name,
            "temperature": p.temperature,
            "max_tokens": p.max_tokens,
            "is_active": p.is_active,
            "created_at": p.created_at,
        }

    return {
        "parsing_provider_id": parsing_id,
        "scoring_provider_id": scoring_id,
        "parsing_provider": await _resolve(parsing_id),
        "scoring_provider": await _resolve(scoring_id),
    }


@api.put("/config/task-assignments")
async def update_task_assignments(
    payload: TaskAssignmentUpdate,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBSystemSettings).where(DBSystemSettings.id == "task_assignments")
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()
    if not settings:
        settings = DBSystemSettings(id="task_assignments")
        session.add(settings)
    for field in ("parsing_provider_id", "scoring_provider_id"):
        val = getattr(payload, field)
        if val:
            p_stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.id == val)
            p_res = await session.execute(p_stmt)
            exists = p_res.scalar_one_or_none()
            if not exists:
                raise HTTPException(400, f"Provider untuk {field} tidak ditemukan")
            setattr(settings, field, val)
        else:
            setattr(settings, field, None)
    await session.commit()
    return {
        "status": "saved",
        "parsing_provider_id": settings.parsing_provider_id,
        "scoring_provider_id": settings.scoring_provider_id,
    }


# ============ DASHBOARD ============
@api.get("/dashboard/stats")
async def dashboard_stats(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    active_jobs = (await session.execute(select(func.count()).select_from(DBJobPosting).where(DBJobPosting.status == "active"))).scalar() or 0
    total_jobs = (await session.execute(select(func.count()).select_from(DBJobPosting))).scalar() or 0
    total_candidates = (await session.execute(select(func.count()).select_from(DBCandidate))).scalar() or 0
    total_screenings = (await session.execute(select(func.count()).select_from(DBScreeningResult))).scalar() or 0

    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    processed_today = (await session.execute(select(func.count()).select_from(DBCandidate).where(DBCandidate.created_at.like(f"{today_iso}%")))).scalar() or 0

    stmt_dist = select(
        func.sum(case(((DBScreeningResult.total_score >= 0) & (DBScreeningResult.total_score < 40), 1), else_=0)).label("low"),
        func.sum(case(((DBScreeningResult.total_score >= 40) & (DBScreeningResult.total_score < 75), 1), else_=0)).label("mid"),
        func.sum(case((DBScreeningResult.total_score >= 75, 1), else_=0)).label("high")
    )
    dist_res = await session.execute(stmt_dist)
    dist_row = dist_res.first()
    dist = {
        "low": int(dist_row.low or 0) if dist_row else 0,
        "mid": int(dist_row.mid or 0) if dist_row else 0,
        "high": int(dist_row.high or 0) if dist_row else 0,
    }

    recent_jobs_stmt = select(DBJobPosting).order_by(desc(DBJobPosting.created_at)).limit(5)
    recent_jobs_res = await session.execute(recent_jobs_stmt)
    recent_jobs = [_job_to_dict(j) for j in recent_jobs_res.scalars().all()]

    return {
        "active_jobs": active_jobs,
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
        "total_screenings": total_screenings,
        "processed_today": processed_today,
        "score_distribution": dist,
        "recent_jobs": recent_jobs,
    }


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

