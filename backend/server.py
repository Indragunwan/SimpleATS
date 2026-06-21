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
    DBAISearchLog,
)
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env", override=True)

from ai_service import (  # noqa: E402
    calculate_total_score,
    call_llm,
    evaluate_match,
    extract_jd_criteria,
    parse_cv,
    recommendation_from_score,
    generate_embedding,
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
    GoogleLoginRequest,
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

connect_args = {}
if "postgresql" in DATABASE_URL:
    connect_args["ssl"] = False

engine = create_async_engine(DATABASE_URL, connect_args=connect_args, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Auto create tables and migrate if database is ready (with retries for startup timing)
    max_retries = 15
    retry_interval = 2
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS embeddings_provider_id VARCHAR(36);"))
            logger.info("Successfully connected to database and migrated tables.")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_interval} seconds...")
            await asyncio.sleep(retry_interval)
        
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

# ============ SECURITY MIDDLEWARES ============
import time
from fastapi.responses import JSONResponse

# In-memory request history for IP-based rate limiting (H2)
RATE_LIMIT_DURATION = 60  # seconds
RATE_LIMIT_REQUESTS = 200  # max requests per minute

request_history = {}

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Only apply rate limiting to /api endpoints, exclude health checks
    if request.url.path.startswith("/api") and not request.url.path.endswith("/health"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean and filter past timestamps within window
        if client_ip in request_history:
            request_history[client_ip] = [t for t in request_history[client_ip] if now - t < RATE_LIMIT_DURATION]
        else:
            request_history[client_ip] = []
            
        if len(request_history[client_ip]) >= RATE_LIMIT_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Terlalu banyak permintaan. Silakan coba lagi nanti (Batas kecepatan terlampaui)."}
            )
            
        request_history[client_ip].append(now)
        
    return await call_next(request)


@app.middleware("http")
async def add_security_headers_middleware(request, call_next):
    response = await call_next(request)
    # Add modern security headers to prevent sniffing, framing, and XSS (M1)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


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
    
    status = job.status
    if job.end_date and status == "active":
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str > job.end_date:
            status = "closed"

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
        "status": status,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "extraction_status": job.extraction_status,
        "extraction_error": job.extraction_error,
        "start_date": job.start_date,
        "end_date": job.end_date,
        "location": job.location,
    }


def _is_job_closed(job: DBJobPosting) -> bool:
    if not job:
        return False
    if job.status == "closed":
        return True
    if job.end_date and job.status == "active":
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str > job.end_date:
            return True
    return False




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
    email_lower = payload.email.lower()
    if email_lower == "admin@demo.com":
        email_lower = "hrdaplzoommeeting@gmail.com"
        
    stmt = select(DBUser).where(DBUser.email == email_lower)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status_code=401, detail="Email atau akun tidak aktif")
        
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


@api.post("/auth/google-login", response_model=LoginResponse)
async def google_login(payload: GoogleLoginRequest, session: AsyncSession = Depends(get_db)) -> LoginResponse:
    import httpx
    
    token = payload.credential
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        except Exception as e:
            logger.error(f"Error calling Google tokeninfo: {e}")
            raise HTTPException(status_code=401, detail="Gagal memverifikasi token Google")
            
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token Google tidak valid atau kedaluwarsa")
        id_info = resp.json()
        
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if google_client_id and id_info.get("aud") != google_client_id:
        logger.warning(f"OAuth audience mismatch: got {id_info.get('aud')}, expected {google_client_id}")
        raise HTTPException(status_code=401, detail="Audience token tidak cocok")
        
    if id_info.get("email_verified") not in ("true", True):
        raise HTTPException(status_code=401, detail="Email Google belum diverifikasi")
        
    email = id_info.get("email").lower()
    
    stmt = select(DBUser).where(DBUser.email == email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Email Anda belum terdaftar di sistem. Hubungi Admin IT untuk didaftarkan."
        )
        
    if not getattr(user, "is_active", True):
        raise HTTPException(status_code=401, detail="Akun Anda dinonaktifkan")
        
    access_token = create_access_token(user.id, user.role, user.email)
    return LoginResponse(
        access_token=access_token,
        user=UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=getattr(user, "is_active", True),
            created_at=user.created_at,
        )
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
        password_hash=hash_password(payload.password or "google-oauth-only-no-password-hash-dummy-value"),
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


@api.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    user: dict = Depends(require_roles("admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if user_id == user["id"]:
        raise HTTPException(400, "Anda tidak dapat menghapus akun Anda sendiri")
    stmt = select(DBUser).where(DBUser.id == user_id)
    res = await session.execute(stmt)
    db_user = res.scalar_one_or_none()
    if not db_user:
        raise HTTPException(404, "User tidak ditemukan")
    await session.delete(db_user)
    await session.commit()
    return {"message": "User berhasil dihapus"}

# ============ JOB POSTINGS ============
@api.post("/jobs")
async def create_job(
    title: str = Form(...),
    raw_jd_text: str = Form(""),
    raw_spec_text: str = Form(""),
    target_position: str = Form(""),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
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
        target_position=target_position.strip(),
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
        start_date=start_date,
        end_date=end_date,
        location=location,
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
        
        # AI extraction: only override target_position if user didn't provide one
        extracted_position = extracted.get("target_position", "")
        if not db_job.target_position and extracted_position:
            db_job.target_position = extracted_position
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
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
    # Block modifications to core criteria/weights for closed/expired jobs
    # Allow metadata (title, dates, location, status) to be updated so they can be re-opened.
    blocked_keys_for_closed = {"criteria", "weights", "responsibilities", "education_requirement", "education_level", "education_major", "min_experience_years"}
    attempted_blocked_keys = blocked_keys_for_closed.intersection(update_data.keys())
    if attempted_blocked_keys and _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup. Kriteria dan bobot tidak dapat dimodifikasi.")
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dimodifikasi")
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
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
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dimodifikasi")
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
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
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dimodifikasi")
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dimodifikasi")
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dimodifikasi")
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
        "weights": weights,
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

    parsing_usage = parsed.get("_usage", {}) or {}
    scoring_usage = evaluation.get("_usage", {}) or {}
    prompt_tokens = int(parsing_usage.get("prompt_tokens", 0)) + int(scoring_usage.get("prompt_tokens", 0))
    completion_tokens = int(parsing_usage.get("completion_tokens", 0)) + int(scoring_usage.get("completion_tokens", 0))
    total_tokens = int(parsing_usage.get("total_tokens", 0)) + int(scoring_usage.get("total_tokens", 0))

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
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    session.add(sr)
    await session.commit()
    return sr_id


# Semaphore global untuk memproses screening LLM satu demi satu secara bergantian (Queue)
# Hal ini mencegah overload request bersamaan ke AI yang memicu '504 Gateway Time-out'
LLM_SEMAPHORE = asyncio.Semaphore(1)


def _build_cv_search_text(cand_name: str, parsed: dict) -> str:
    summary = parsed.get("summary") or ""
    
    # Handle list of objects vs list of strings for skills
    skills_list = parsed.get("skills", []) or []
    skills_str_list = []
    for s in skills_list:
        if isinstance(s, dict):
            skills_str_list.append(s.get("skill_name", ""))
        elif isinstance(s, str):
            skills_str_list.append(s)
    skills = ", ".join(skills_str_list)
    
    hard_skills = ", ".join(parsed.get("hard_skills", []) or [])
    soft_skills = ", ".join(parsed.get("soft_skills", []) or [])
    
    edu_list = []
    for edu in parsed.get("education", []) or []:
        degree = edu.get("degree") or ""
        inst = edu.get("institution") or ""
        degree_str = degree.get("degree") if isinstance(degree, dict) else degree
        inst_str = inst.get("institution") if isinstance(inst, dict) else inst
        edu_list.append(f"{degree_str} di {inst_str}")
    edu_str = ", ".join(edu_list)
    
    work_list = []
    history = parsed.get("experience") or parsed.get("work_history") or []
    for w in history:
        if isinstance(w, dict):
            pos = w.get("role") or w.get("position") or ""
            comp = w.get("company") or ""
            work_list.append(f"{pos} di {comp}")
    work_str = ", ".join(work_list)
    
    parts = []
    if cand_name: parts.append(f"Nama: {cand_name}")
    if summary: parts.append(f"Ringkasan: {summary}")
    if skills: parts.append(f"Keahlian: {skills}")
    if hard_skills: parts.append(f"Keahlian Teknis: {hard_skills}")
    if soft_skills: parts.append(f"Keahlian Non-Teknis: {soft_skills}")
    if edu_str: parts.append(f"Pendidikan: {edu_str}")
    if work_str: parts.append(f"Pengalaman Kerja: {work_str}")
    
    return "\n".join(parts)



async def _process_candidate(candidate_id: str, job_id: str) -> None:
    """Background task: parse CV + evaluate against JD."""
    async with LLM_SEMAPHORE:
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
                parsed_name = parsed.get("name")
                if parsed_name and parsed_name != "Unknown" and parsed_name.strip():
                    cand.name = parsed_name.strip()
                elif not cand.name or cand.name == "Memproses...":
                    cand.name = cand.file_name or "Unknown"
                cand.email = parsed.get("email", "")
                cand.phone = parsed.get("phone", "")
                cand.parsed = parsed
                cand.status = "parsed"
                
                # Generate cv_embedding
                try:
                    from ai_service import generate_embedding
                    embeddings_cfg = await _get_ai_config_for_task(session, "embeddings")
                    search_text = _build_cv_search_text(cand.name, parsed)
                    cand.cv_embedding = await generate_embedding(search_text, embeddings_cfg)
                except Exception as emb_err:
                    logger.error(f"Gagal generate embedding untuk kandidat {candidate_id}: {emb_err}")
                
                await session.commit()
                
                await _screen_candidate_for_job(session, candidate_id, job_id, parsed, scoring_cfg)
        except Exception as e:
            logger.exception("Candidate processing failed")
            error_msg = f"{type(e).__name__}: {str(e)}" if str(e) else repr(e)
            if "ReadTimeout" in error_msg or "timeout" in error_msg.lower():
                error_msg = f"Koneksi AI Timeout (Batas waktu habis saat menganalisis CV). Silakan klik 'Screening Ulang' untuk mencoba kembali. Detail: {error_msg}"
            elif "API key" in error_msg or "Authorization" in error_msg:
                error_msg = f"Konfigurasi API Key AI tidak valid atau tidak ditemukan di server. Detail: {error_msg}"
            elif "JSONDecodeError" in error_msg or "json" in error_msg.lower():
                error_msg = f"Gagal mengekstrak data dari respons AI (Format JSON tidak sesuai). Detail: {error_msg}"
            
            async with async_session() as session:
                stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
                res = await session.execute(stmt)
                cand = res.scalar_one_or_none()
                if cand:
                    cand.status = "failed"
                    cand.error_message = error_msg
                    if not cand.name or cand.name == "Memproses...":
                        cand.name = cand.file_name or "Unknown"
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


def sanitize_filename(filename: str) -> str:
    import re
    # Extract name and extension
    name, ext = os.path.splitext(filename)
    # Strip non-alphanumeric/safe characters from the name
    name = re.sub(r'[^a-zA-Z0-9_\-\s]', '', name).strip()
    # Strip unsafe characters from extension
    ext = re.sub(r'[^a-zA-Z0-9]', '', ext).strip()
    if not name:
        name = "cv"
    if not ext:
        ext = "txt"
    return f"{name}.{ext}"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".doc"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@api.post("/jobs/{job_id}/upload-cv")
async def upload_cv(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if _is_job_closed(job):
        raise HTTPException(400, "Lowongan sudah ditutup, CV tidak dapat diunggah")
    if len(files) > 500:
        raise HTTPException(400, "Maksimum 500 CV per sesi")
    import uuid

    created_ids: list[str] = []
    for f in files:
        filename = f.filename or "cv.txt"
        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format file '{filename}' tidak didukung. Harap unggah file PDF, DOCX, atau TXT."
            )
            
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Ukuran file '{filename}' terlalu besar. Batas maksimum adalah 10MB."
            )
            
        safe_name = sanitize_filename(filename)
        text = extract_text(safe_name, content)
        import re
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text).strip()
        cid = str(uuid.uuid4())
        
        # Save file to uploads directory
        uploads_dir = Path(__file__).parent / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path = uploads_dir / f"{cid}_{safe_name}"
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(content)
        except Exception as e:
            logger.error(f"Gagal menyimpan file CV: {e}")
            raise HTTPException(500, f"Gagal menyimpan file CV {filename}")

        # Save extracted text as .md for inspection
        md_name = os.path.splitext(safe_name)[0] + ".md"
        try:
            with open(uploads_dir / md_name, "w", encoding="utf-8") as md_file:
                md_file.write(f"# Ekstraksi: {filename}\n\n{text}")
        except Exception as e:
            logger.warning(f"Gagal menyimpan .md untuk {filename}: {e}")

        # Derive display name from original filename (strip extension, keep unicode)
        original_display = os.path.splitext(filename)[0].strip() or safe_name

        doc = DBCandidate(
            id=cid,
            name=original_display,
            email="",
            phone="",
            file_name=safe_name,
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
            "phone": c.phone or "",
            "file_name": c.file_name,
            "status": c.status,
            "error_message": c.error_message or "",
            "created_at": c.created_at,
        }
        for c in candidates
    }
    scored_ids = {r.candidate_id for r in results}

    out = []
    for r in results:
        c = cand_map.get(r.candidate_id, {})
        c_name = c.get("name")
        c_file = c.get("file_name")
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
                "candidate_name": c_name if (c_name and c_name != "Memproses..." and c_name != "Unknown") else (c_file or "Unknown"),
                "candidate_email": c.get("email", ""),
                "candidate_phone": c.get("phone", ""),
                "candidate_status": c.get("status", "parsed"),
                "candidate_error": c.get("error_message", ""),
                "prompt_tokens": r.prompt_tokens or 0,
                "completion_tokens": r.completion_tokens or 0,
                "total_tokens": r.total_tokens or 0,
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
                    "candidate_name": c.name if (c.name and c.name != "Memproses..." and c.name != "Unknown") else (c.file_name or "Memproses..."),
                    "candidate_email": c.email or "",
                    "candidate_phone": c.phone or "",
                    "candidate_status": c.status or "pending",
                    "candidate_error": c.error_message or "",
                    "total_score": 0,
                    "recommendation": "pending",
                    "decision": "pending",
                    "rationale_summary": "",
                    "created_at": c.created_at,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            )
    return out


@api.get("/candidates/{candidate_id}/cv")
async def get_candidate_cv(
    candidate_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db)
):
    from fastapi.responses import FileResponse
    stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
    res = await session.execute(stmt)
    cand = res.scalar_one_or_none()
    if not cand:
        raise HTTPException(404, "Kandidat tidak ditemukan")
    
    uploads_dir = Path(__file__).parent.joinpath("uploads").resolve()
    # Find file starting with candidate_id
    files = list(uploads_dir.glob(f"{candidate_id}_*"))
    if files:
        path = files[0].resolve()
        # Verify the file is strictly within the uploads directory
        try:
            path.relative_to(uploads_dir)
        except ValueError:
            raise HTTPException(403, "Akses file ditolak (di luar batas uploads)")
    else:
        # Fallback to root directory
        root_dir = Path(__file__).parent.parent.resolve()
        # Strip path traversal elements from cand.file_name
        safe_filename = Path(cand.file_name).name
        fallback_path = root_dir.joinpath(safe_filename).resolve()
        if fallback_path.exists():
            try:
                fallback_path.relative_to(root_dir)
                path = fallback_path
            except ValueError:
                raise HTTPException(403, "Akses file ditolak (di luar batas root)")
        else:
            raise HTTPException(404, f"File CV '{cand.file_name}' tidak ditemukan")
            
    media_type = "application/octet-stream"
    if cand.file_name.lower().endswith(".pdf"):
        media_type = "application/pdf"
    elif cand.file_name.lower().endswith(".png"):
        media_type = "image/png"
    elif cand.file_name.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
        
    return FileResponse(
        path=path,
        filename=cand.file_name,
        media_type=media_type
    )


@api.post("/jobs/{job_id}/candidates/rescreen-all")
async def rescreen_all_candidates(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(DBCandidate).where(DBCandidate.job_posting_id == job_id)
    res = await session.execute(stmt)
    candidates = res.scalars().all()
    
    if not candidates:
        raise HTTPException(400, "Tidak ada kandidat untuk diproses ulang")
        
    for c in candidates:
        c.status = "pending"
        c.error_message = None
        
        # Delete previous screening result if exists
        stmt_sr = select(DBScreeningResult).where(
            and_(
                DBScreeningResult.candidate_id == c.id,
                DBScreeningResult.job_posting_id == job_id
            )
        )
        res_sr = await session.execute(stmt_sr)
        sr = res_sr.scalar_one_or_none()
        if sr:
            await session.delete(sr)
            
    await session.commit()
    
    for c in candidates:
        background_tasks.add_task(_process_candidate, c.id, job_id)
        
    return {"queued": len(candidates)}


@api.post("/jobs/{job_id}/candidates/{candidate_id}/rescreen")
async def rescreen_candidate(
    job_id: str,
    candidate_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    stmt_c = select(DBCandidate).where(
        and_(
            DBCandidate.id == candidate_id,
            DBCandidate.job_posting_id == job_id
        )
    )
    res_c = await session.execute(stmt_c)
    cand = res_c.scalar_one_or_none()
    if not cand:
        raise HTTPException(404, "Kandidat tidak ditemukan")
        
    # Reset candidate status and clear error
    cand.status = "pending"
    cand.error_message = None
    
    # Delete previous screening result if exists
    stmt_sr = select(DBScreeningResult).where(
        and_(
            DBScreeningResult.candidate_id == candidate_id,
            DBScreeningResult.job_posting_id == job_id
        )
    )
    res_sr = await session.execute(stmt_sr)
    sr = res_sr.scalar_one_or_none()
    if sr:
        await session.delete(sr)
        
    await session.commit()
    
    # Process candidate synchronously to await the screening completion
    await _process_candidate(candidate_id, job_id)
    
    # Refresh candidate from database to check the result
    stmt_check = select(DBCandidate).where(DBCandidate.id == candidate_id)
    res_check = await session.execute(stmt_check)
    cand_check = res_check.scalar_one_or_none()
    
    if not cand_check:
        raise HTTPException(404, "Kandidat tidak ditemukan setelah pemrosesan ulang")
        
    if cand_check.status == "failed":
        raise HTTPException(500, cand_check.error_message or "Proses screening ulang gagal")
        
    return {"status": "success"}


@api.delete("/jobs/{job_id}/candidates/{candidate_id}")
async def delete_candidate(
    job_id: str,
    candidate_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
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
    user: dict = Depends(require_roles("hiring_manager", "admin_it")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import func
    # Fetch job first to check if it is closed
    stmt_check = select(DBJobPosting).where(DBJobPosting.id == job_id)
    res_check = await session.execute(stmt_check)
    job_check = res_check.scalar_one_or_none()
    if job_check and _is_job_closed(job_check):
        raise HTTPException(400, "Lowongan sudah ditutup dan tidak dapat dihapus")
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
        "prompt_tokens": sr.prompt_tokens or 0,
        "completion_tokens": sr.completion_tokens or 0,
        "total_tokens": sr.total_tokens or 0,
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
@api.post("/talent-pool/search")
async def search_talent_pool(
    payload: dict,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query pencarian tidak boleh kosong")
        
    embeddings_cfg = await _get_ai_config_for_task(session, "embeddings")
    
    try:
        from ai_service import generate_embedding
        query_embedding = await generate_embedding(query, embeddings_cfg)
    except Exception as e:
        logger.error(f"Gagal generate embedding untuk search query: {e}")
        raise HTTPException(500, f"Gagal memproses pencarian semantik: {str(e)}")
        
    # Get all parsed candidates that have embeddings
    stmt_c = select(DBCandidate).where(
        and_(
            DBCandidate.status == "parsed",
            DBCandidate.cv_embedding.isnot(None)
        )
    )
    res_c = await session.execute(stmt_c)
    candidates = res_c.scalars().all()
    
    # Get stats
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
        
    import numpy as np
    q_vec = np.array(query_embedding)
    q_norm = np.linalg.norm(q_vec)
    
    if q_norm == 0:
        raise HTTPException(500, "AI Provider mengembalikan vektor kosong untuk query ini.")
        
    out = []
    for c in candidates:
        if not c.cv_embedding or len(c.cv_embedding) != len(query_embedding):
            continue
            
        c_vec = np.array(c.cv_embedding)
        c_norm = np.linalg.norm(c_vec)
        if c_norm == 0:
            continue
            
        score = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
        pct_score = max(0.0, min(100.0, (score + 1.0) / 2.0 * 100.0))
        
        s = stats.get(c.id, {})
        parsed = _ensure_dict(c.parsed)
        work_history = parsed.get("work_history", [])
        current_position = ""
        if work_history and isinstance(work_history, list) and len(work_history) > 0:
            if isinstance(work_history[0], dict):
                current_position = work_history[0].get("position", "")
                
        raw_skills = []
        for sk in (parsed.get("skills", []) or []):
            if isinstance(sk, dict):
                raw_skills.append(sk.get("skill_name", ""))
            else:
                raw_skills.append(sk)
        top_skills = raw_skills[:6]

        out.append({
            "id": c.id,
            "name": c.name if (c.name and c.name != "Memproses..." and c.name != "Unknown") else (c.file_name or "Unknown"),
            "email": c.email or "",
            "phone": c.phone or "",
            "years_of_experience": parsed.get("years_of_experience", 0),
            "top_skills": top_skills,
            "current_position": current_position,
            "best_score": s.get("best_score", 0),
            "screenings_count": s.get("screenings_count", 0),
            "shortlisted_count": s.get("shortlisted_count", 0),
            "created_at": c.created_at,
            "similarity_score": round(pct_score, 2)
        })
        
    # Sort by similarity score descending
    out.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    # Filter dan limit hasil
    # Hanya ambil yang similarity score nya >= 65% dan maksimal top 15 untuk LLM RAG
    filtered_out = [x for x in out if x["similarity_score"] >= 65.0][:15]
    
    if not filtered_out:
        # Still get cumulative usage
        stmt_sum = select(
            func.sum(DBAISearchLog.prompt_tokens).label("prompt_sum"),
            func.sum(DBAISearchLog.completion_tokens).label("completion_sum"),
            func.sum(DBAISearchLog.total_tokens).label("total_sum")
        )
        res_sum = await session.execute(stmt_sum)
        sum_row = res_sum.first()
        cumulative_prompt = int(sum_row.prompt_sum or 0) if sum_row else 0
        cumulative_completion = int(sum_row.completion_sum or 0) if sum_row else 0
        cumulative_total = int(sum_row.total_sum or 0) if sum_row else 0
        
        USD_TO_IDR = 17900
        cum_cost_usd = (cumulative_prompt * 0.30 / 1000000) + (cumulative_completion * 2.50 / 1000000)
        cum_cost_rp = round(cum_cost_usd * USD_TO_IDR, 2)
        
        return {
            "candidates": [],
            "search_usage": None,
            "cumulative_usage": {
                "prompt_tokens": cumulative_prompt,
                "completion_tokens": cumulative_completion,
                "total_tokens": cumulative_total,
                "cost_rp": cum_cost_rp
            }
        }
        
    # Tahap 2: AI Chat Filtering (RAG)
    try:
        scoring_cfg = await _get_ai_config_for_task(session, "scoring")
        
        # Prepare lightweight candidate profiles for LLM
        candidate_profiles = []
        for c_dict in filtered_out:
            # Cari dari object candidates yang sudah ada
            c_obj = next((cand for cand in candidates if cand.id == c_dict["id"]), None)
            if c_obj:
                parsed_data = _ensure_dict(c_obj.parsed)
                education = parsed_data.get("education", [])
                edu_str = ", ".join([f"{e.get('degree','')} {e.get('major','')} at {e.get('institution','')}" for e in education if isinstance(e, dict)])
            else:
                edu_str = ""
            
            candidate_profiles.append({
                "id": c_dict["id"],
                "name": c_dict["name"],
                "current_position": c_dict["current_position"],
                "skills": c_dict["top_skills"],
                "education": edu_str,
                "experience_years": c_dict["experience_years"] if "experience_years" in c_dict else c_dict["years_of_experience"]
            })
            
        import json
        profiles_json = json.dumps(candidate_profiles, ensure_ascii=False)
        
        sys_prompt = (
            "You are an expert HR AI assistant. Your task is to filter a list of candidates based on the user's search query, allowing for semantic flexibility.\n"
            "Return a JSON object with a single key 'matched_candidates' containing an array of objects.\n"
            "Each object must have 'id' (the candidate ID) and 'ai_reason' (a brief 1-2 sentence explanation of why they match the query, in Indonesian).\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Allow semantic flexibility and treat related terms or minor terminology differences as matches (e.g., treat 'React' and 'ReactJS', or 'Frontend' and 'Web Developer', or 'HSE' and 'Safety Officer' as matches).\n"
            "2. Do not outright reject candidates based on minor terminology differences. For education level and major (e.g., 'S1 Ekonomi'), allow closely related majors or equivalent degrees (e.g. 'S1 Akuntansi' or 'S1 Manajemen' if they fit the role's context).\n"
            "3. If a candidate matches the search query semantically, include them in the 'matched_candidates' list.\n"
            "4. If no candidates match, return the JSON object with an empty array: {\"matched_candidates\": []}."
        )
        user_prompt = f"User Search Query: '{query}'\n\nCandidates:\n{profiles_json}"

        
        llm_response = await asyncio.wait_for(
            call_llm(sys_prompt, user_prompt, scoring_cfg, response_format={"type": "json_object"}),
            timeout=45
        )
        
        # Track token usage of the search query
        usage = getattr(llm_response, "usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or 0)
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
            
        # Log to DBAISearchLog
        import uuid
        from models import DBAISearchLog
        search_log = DBAISearchLog(
            id=str(uuid.uuid4()),
            query=query,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        session.add(search_log)
        await session.commit()
        
        try:
            llm_data = json.loads(llm_response)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if match:
                llm_data = json.loads(match.group(0))
            else:
                llm_data = {"matched_candidates": []}
                
        matched_list = llm_data.get("matched_candidates", [])
        # handle possible string IDs or int IDs
        matched_dict = {str(item["id"]): item.get("ai_reason", "") for item in matched_list if "id" in item}
        
        final_out = []
        for c in filtered_out:
            cid_str = str(c["id"])
            if cid_str in matched_dict:
                c["ai_reason"] = matched_dict[cid_str]
                final_out.append(c)
                
        # Calculate cost
        USD_TO_IDR = 17900
        cost_usd = (prompt_tokens * 0.30 / 1000000) + (completion_tokens * 2.50 / 1000000)
        cost_rp = round(cost_usd * USD_TO_IDR, 2)
        
        # Get cumulative usage
        stmt_sum = select(
            func.sum(DBAISearchLog.prompt_tokens).label("prompt_sum"),
            func.sum(DBAISearchLog.completion_tokens).label("completion_sum"),
            func.sum(DBAISearchLog.total_tokens).label("total_sum")
        )
        res_sum = await session.execute(stmt_sum)
        sum_row = res_sum.first()
        cumulative_prompt = int(sum_row.prompt_sum or 0) if sum_row else 0
        cumulative_completion = int(sum_row.completion_sum or 0) if sum_row else 0
        cumulative_total = int(sum_row.total_sum or 0) if sum_row else 0
        
        cum_cost_usd = (cumulative_prompt * 0.30 / 1000000) + (cumulative_completion * 2.50 / 1000000)
        cum_cost_rp = round(cum_cost_usd * USD_TO_IDR, 2)
        
        return {
            "candidates": final_out,
            "search_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_rp": cost_rp
            },
            "cumulative_usage": {
                "prompt_tokens": cumulative_prompt,
                "completion_tokens": cumulative_completion,
                "total_tokens": cumulative_total,
                "cost_rp": cum_cost_rp
            }
        }
        
    except Exception as e:
        logger.error(f"RAG Filtering failed: {e}")
        raise HTTPException(500, f"Gagal memproses penyaringan AI: {str(e)}")


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
        raw_skills = []
        for sk in (parsed.get("skills", []) or []):
            if isinstance(sk, dict):
                raw_skills.append(sk.get("skill_name", ""))
            else:
                raw_skills.append(sk)
        top_skills = raw_skills[:6]

        out.append(
            {
                "id": c.id,
                "name": c.name if (c.name and c.name != "Memproses..." and c.name != "Unknown") else (c.file_name or "Unknown"),
                "email": c.email or "",
                "phone": c.phone or "",
                "years_of_experience": parsed.get("years_of_experience", 0),
                "top_skills": top_skills,
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
            "prompt_tokens": s.prompt_tokens or 0,
            "completion_tokens": s.completion_tokens or 0,
            "total_tokens": s.total_tokens or 0,
        })
    cand_dict = {
        "id": cand.id,
        "name": cand.name if (cand.name and cand.name != "Memproses..." and cand.name != "Unknown") else (cand.file_name or "Unknown"),
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
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
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
        is_embedding_model = "embed" in (cfg.get("model_name") or "").lower()
        if is_embedding_model:
            result = await asyncio.wait_for(
                generate_embedding("Test connection", cfg),
                timeout=60,
            )
            if isinstance(result, list) and len(result) > 0:
                return {"success": True, "response": f"Embedding vector generated successfully with {len(result)} dimensions."}
            else:
                return {"success": False, "error": "No vector returned from embedding API."}
        else:
            result = await asyncio.wait_for(
                call_llm(
                    "You are a connectivity test. Respond with the exact text: OK",
                    "Reply OK only.",
                    cfg,
                ),
                timeout=60,
            )
            return {"success": True, "response": result[:200]}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Koneksi habis waktu / Timeout (Kemungkinan cold-start atau API sedang sangat lambat). Silakan coba lagi."}
    except Exception as e:
        err_msg = str(e) or type(e).__name__
        return {"success": False, "error": err_msg[:300]}


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
        is_embedding_model = "embed" in (cfg.get("model_name") or "").lower()
        if is_embedding_model:
            result = await asyncio.wait_for(
                generate_embedding("Test connection", cfg),
                timeout=60,
            )
            if isinstance(result, list) and len(result) > 0:
                return {"success": True, "response": f"Embedding vector generated successfully with {len(result)} dimensions."}
            else:
                return {"success": False, "error": "No vector returned from embedding API."}
        else:
            result = await asyncio.wait_for(
                call_llm(
                    "You are a connectivity test. Respond with the exact text: OK",
                    "Reply OK only.",
                    cfg,
                ),
                timeout=60,
            )
            return {"success": True, "response": result[:200]}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Koneksi habis waktu / Timeout (Kemungkinan cold-start atau API sedang sangat lambat). Silakan coba lagi."}
    except Exception as e:
        err_msg = str(e) or type(e).__name__
        return {"success": False, "error": err_msg[:300]}



# ============ TASK MODEL ASSIGNMENTS ============
class TaskAssignmentUpdate(BaseModel):
    parsing_provider_id: Optional[str] = None
    scoring_provider_id: Optional[str] = None
    embeddings_provider_id: Optional[str] = None



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
    embeddings_id = settings.embeddings_provider_id if settings else None

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
        "embeddings_provider_id": embeddings_id,
        "parsing_provider": await _resolve(parsing_id),
        "scoring_provider": await _resolve(scoring_id),
        "embeddings_provider": await _resolve(embeddings_id),
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
    for field in ("parsing_provider_id", "scoring_provider_id", "embeddings_provider_id"):
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
        "embeddings_provider_id": settings.embeddings_provider_id,
    }


# ============ DASHBOARD ============
@api.get("/dashboard/stats")
async def dashboard_stats(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    today_str = datetime.now().strftime("%Y-%m-%d")
    active_jobs = (await session.execute(
        select(func.count())
        .select_from(DBJobPosting)
        .where(
            and_(
                DBJobPosting.status == "active",
                or_(
                    DBJobPosting.end_date.is_(None),
                    DBJobPosting.end_date == "",
                    DBJobPosting.end_date >= today_str
                )
            )
        )
    )).scalar() or 0
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

    # Calculate token usage from screening results
    stmt_scr_tokens = select(
        func.sum(DBScreeningResult.prompt_tokens).label("prompt_sum"),
        func.sum(DBScreeningResult.completion_tokens).label("completion_sum"),
        func.sum(DBScreeningResult.total_tokens).label("total_sum")
    )
    res_scr_tokens = await session.execute(stmt_scr_tokens)
    scr_tokens_row = res_scr_tokens.first()
    scr_prompt = int(scr_tokens_row.prompt_sum or 0) if scr_tokens_row else 0
    scr_completion = int(scr_tokens_row.completion_sum or 0) if scr_tokens_row else 0
    scr_total = int(scr_tokens_row.total_sum or 0) if scr_tokens_row else 0

    # Calculate token usage from AI search logs
    stmt_search_tokens = select(
        func.sum(DBAISearchLog.prompt_tokens).label("prompt_sum"),
        func.sum(DBAISearchLog.completion_tokens).label("completion_sum"),
        func.sum(DBAISearchLog.total_tokens).label("total_sum")
    )
    res_search_tokens = await session.execute(stmt_search_tokens)
    search_tokens_row = res_search_tokens.first()
    search_prompt = int(search_tokens_row.prompt_sum or 0) if search_tokens_row else 0
    search_completion = int(search_tokens_row.completion_sum or 0) if search_tokens_row else 0
    search_total = int(search_tokens_row.total_sum or 0) if search_tokens_row else 0

    grand_prompt = scr_prompt + search_prompt
    grand_completion = scr_completion + search_completion
    grand_total = scr_total + search_total

    # Cost Gemini 2.5 Flash: input: $0.30/1M, output: $2.50/1M, kurs $1 = Rp17.900
    USD_TO_IDR = 17900
    grand_cost_usd = (grand_prompt * 0.30 / 1000000) + (grand_completion * 2.50 / 1000000)
    grand_cost_rp = round(grand_cost_usd * USD_TO_IDR, 2)

    return {
        "active_jobs": active_jobs,
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
        "total_screenings": total_screenings,
        "processed_today": processed_today,
        "score_distribution": dist,
        "recent_jobs": recent_jobs,
        "total_tokens_used": grand_total,
        "total_prompt_tokens": grand_prompt,
        "total_completion_tokens": grand_completion,
        "total_rupiah_cost": grand_cost_rp,
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
    port = int(os.environ.get("PORT", 9482))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)

# Production lockdown complete 2026-05-30

