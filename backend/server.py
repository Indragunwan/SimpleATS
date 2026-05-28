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
from motor.motor_asyncio import AsyncIOMotorClient
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

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await seed_demo_users(db)
    await seed_default_ai_config(db)
    await backfill_criteria_ids(db)
    logger.info("Startup complete")
    try:
        yield
    finally:
        # Shutdown
        client.close()


app = FastAPI(title="Sistem Penapisan CV Berbasis AI", lifespan=lifespan)
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cv-screening")


def _clean(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
    return doc


async def _get_active_ai_config() -> dict:
    cfg = await db.ai_provider_configs.find_one({"is_active": True}, {"_id": 0})
    if not cfg:
        cfg = {
            "provider_type": "emergent",
            "llm_provider": "anthropic",
            "model_name": "claude-sonnet-4-6",
            "temperature": 0.2,
            "max_tokens": 4000,
        }
    return cfg


async def _get_ai_config_for_task(task: str) -> dict:
    """Get AI config for a specific task (parsing | scoring).
    Falls back to the default active provider when no assignment is set.

    Tasks:
      parsing → JD extraction + CV parsing (structural, deterministic)
      scoring → Semantic matching + rationale (judgment, narrative)
    """
    settings = await db.system_settings.find_one({"id": "task_assignments"}, {"_id": 0})
    if settings:
        key = f"{task}_provider_id"
        provider_id = settings.get(key)
        if provider_id:
            cfg = await db.ai_provider_configs.find_one({"id": provider_id}, {"_id": 0})
            if cfg:
                return cfg
    return await _get_active_ai_config()


# Lifespan-based startup/shutdown handled via `lifespan` contextmanager above.


# ============ HEALTH ============
@api.get("/health")
async def health() -> dict:
    db_ok = False
    try:
        await db.command("ping")
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
async def login(payload: LoginRequest) -> LoginResponse:
    user = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau kata sandi salah")
    token = create_access_token(user["id"], user["role"], user["email"])
    return LoginResponse(
        access_token=token,
        user=UserOut(
            id=user["id"],
            name=user["name"],
            email=user["email"],
            role=user["role"],
            is_active=user.get("is_active", True),
            created_at=user["created_at"],
        ),
    )


@api.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)) -> UserOut:
    doc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    return UserOut(**{k: doc[k] for k in ("id", "name", "email", "role", "is_active", "created_at")})


# ============ USER MANAGEMENT (Admin) ============
@api.get("/users", response_model=list[UserOut])
async def list_users(user: dict = Depends(require_roles("admin_it"))) -> list[UserOut]:
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [UserOut(**d) for d in docs]


@api.post("/users", response_model=UserOut)
async def create_user(
    payload: UserCreate, user: dict = Depends(require_roles("admin_it"))
) -> UserOut:
    if payload.role not in ("hr_recruiter", "hiring_manager", "admin_it"):
        raise HTTPException(400, "Role tidak valid")
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(400, "Email sudah terdaftar")
    import uuid

    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    return UserOut(**{k: doc[k] for k in ("id", "name", "email", "role", "is_active", "created_at")})


@api.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    user: dict = Depends(require_roles("admin_it")),
) -> UserOut:
    update: dict = {}
    if payload.name is not None:
        update["name"] = payload.name
    if payload.role is not None:
        if payload.role not in ("hr_recruiter", "hiring_manager", "admin_it"):
            raise HTTPException(400, "Role tidak valid")
        update["role"] = payload.role
    if payload.is_active is not None:
        update["is_active"] = payload.is_active
    if payload.password:
        update["password_hash"] = hash_password(payload.password)
    if not update:
        raise HTTPException(400, "Tidak ada perubahan")
    res = await db.users.find_one_and_update(
        {"id": user_id}, {"$set": update}, return_document=True
    )
    if not res:
        raise HTTPException(404, "User tidak ditemukan")
    res = _clean(res)
    return UserOut(**{k: res[k] for k in ("id", "name", "email", "role", "is_active", "created_at")})


# ============ JOB POSTINGS ============
@api.post("/jobs")
async def create_job(
    title: str = Form(...),
    department: str = Form(""),
    raw_jd_text: str = Form(""),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
) -> dict:
    import uuid

    text = raw_jd_text or ""
    file_name = None
    if file:
        content = await file.read()
        text = extract_text(file.filename or "jd.txt", content)
        file_name = file.filename
    if not text or len(text.strip()) < 20:
        raise HTTPException(400, "Teks JD terlalu pendek atau kosong")

    job_id = str(uuid.uuid4())
    doc = {
        "id": job_id,
        "title": title,
        "department": department,
        "raw_jd_text": text,
        "file_name": file_name,
        "target_position": "",
        "min_experience_years": 0,
        "education_requirement": "",
        "education_level": "",
        "education_major": "",
        "responsibilities": [],
        "criteria": [],
        "weights": {
            "must_have": 40,
            "experience": 30,
            "domain": 15,
            "education": 5,
            "nice_have": 10,
            "edu_level_pct": 70,
            "edu_major_pct": 30,
            "shortlist_threshold": 75,
            "reject_threshold": 40,
        },
        "status": "draft",
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "extraction_status": "processing",
    }
    await db.job_postings.insert_one(doc)

    # Trigger extraction (sync but fast - LLM call ~5-15s)
    try:
        cfg = await _get_ai_config_for_task("parsing")
        extracted = await extract_jd_criteria(text, cfg)
        import uuid as _u

        criteria = []
        for v in extracted.get("must_have", []):
            criteria.append({"id": str(_u.uuid4()), "type": "must", "category": "skill", "value": v, "weight": 3})
        for v in extracted.get("nice_to_have", []):
            criteria.append({"id": str(_u.uuid4()), "type": "nice", "category": "skill", "value": v, "weight": 3})
        await db.job_postings.update_one(
            {"id": job_id},
            {
                "$set": {
                    "target_position": extracted.get("target_position", ""),
                    "min_experience_years": extracted.get("min_experience_years", 0),
                    "education_requirement": extracted.get("education_requirement", ""),
                    "education_level": extracted.get("education_level", ""),
                    "education_major": extracted.get("education_major", ""),
                    "responsibilities": extracted.get("responsibilities", []),
                    "criteria": criteria,
                    "extraction_status": "done",
                    "status": "active",
                }
            },
        )
    except Exception as e:
        logger.exception("JD extraction failed")
        await db.job_postings.update_one(
            {"id": job_id},
            {"$set": {"extraction_status": "failed", "extraction_error": str(e)}},
        )

    doc = await db.job_postings.find_one({"id": job_id}, {"_id": 0})
    return doc


@api.get("/jobs")
async def list_jobs(user: dict = Depends(get_current_user)) -> list[dict]:
    docs = await db.job_postings.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Attach candidate counts
    for d in docs:
        d["candidate_count"] = await db.screening_results.count_documents({"job_posting_id": d["id"]})
    return docs


@api.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    doc = await db.job_postings.find_one({"id": job_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "JD tidak ditemukan")
    return doc


@api.patch("/jobs/{job_id}")
async def update_job(
    job_id: str,
    payload: JobPostingUpdate,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
) -> dict:
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(400, "Tidak ada perubahan")
    res = await db.job_postings.find_one_and_update(
        {"id": job_id}, {"$set": update}, return_document=True
    )
    if not res:
        raise HTTPException(404, "JD tidak ditemukan")
    return _clean(res)


@api.post("/jobs/{job_id}/reextract")
async def reextract_job(
    job_id: str, user: dict = Depends(require_roles("hr_recruiter", "admin_it"))
) -> dict:
    job = await db.job_postings.find_one({"id": job_id})
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    cfg = await _get_ai_config_for_task("parsing")
    extracted = await extract_jd_criteria(job["raw_jd_text"], cfg)
    import uuid as _u

    criteria = []
    for v in extracted.get("must_have", []):
        criteria.append({"id": str(_u.uuid4()), "type": "must", "category": "skill", "value": v, "weight": 3})
    for v in extracted.get("nice_to_have", []):
        criteria.append({"id": str(_u.uuid4()), "type": "nice", "category": "skill", "value": v, "weight": 3})
    await db.job_postings.update_one(
        {"id": job_id},
        {
            "$set": {
                "target_position": extracted.get("target_position", ""),
                "min_experience_years": extracted.get("min_experience_years", 0),
                "education_requirement": extracted.get("education_requirement", ""),
                "education_level": extracted.get("education_level", ""),
                "education_major": extracted.get("education_major", ""),
                "responsibilities": extracted.get("responsibilities", []),
                "criteria": criteria,
                "extraction_status": "done",
            }
        },
    )
    return await db.job_postings.find_one({"id": job_id}, {"_id": 0})


# ============ JD CRITERIA CRUD ============
@api.post("/jobs/{job_id}/criteria")
async def add_criterion(
    job_id: str,
    payload: CriterionInput,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    if payload.type not in ("must", "nice"):
        raise HTTPException(400, "Tipe harus 'must' atau 'nice'")
    if not (1 <= payload.weight <= 5):
        raise HTTPException(400, "Bobot harus 1-5")
    if not payload.value.strip():
        raise HTTPException(400, "Nilai kriteria tidak boleh kosong")
    import uuid as _u

    item = {
        "id": str(_u.uuid4()),
        "type": payload.type,
        "category": payload.category or "skill",
        "value": payload.value.strip(),
        "weight": payload.weight,
    }
    res = await db.job_postings.update_one(
        {"id": job_id}, {"$push": {"criteria": item}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "JD tidak ditemukan")
    return item


@api.patch("/jobs/{job_id}/criteria/{criterion_id}")
async def update_criterion(
    job_id: str,
    criterion_id: str,
    payload: CriterionInput,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    if payload.type not in ("must", "nice"):
        raise HTTPException(400, "Tipe harus 'must' atau 'nice'")
    if not (1 <= payload.weight <= 5):
        raise HTTPException(400, "Bobot harus 1-5")
    res = await db.job_postings.update_one(
        {"id": job_id, "criteria.id": criterion_id},
        {
            "$set": {
                "criteria.$.type": payload.type,
                "criteria.$.category": payload.category or "skill",
                "criteria.$.value": payload.value.strip(),
                "criteria.$.weight": payload.weight,
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Kriteria tidak ditemukan")
    return {"status": "updated"}


@api.delete("/jobs/{job_id}/criteria/{criterion_id}")
async def delete_criterion(
    job_id: str,
    criterion_id: str,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    res = await db.job_postings.update_one(
        {"id": job_id}, {"$pull": {"criteria": {"id": criterion_id}}}
    )
    if res.modified_count == 0:
        raise HTTPException(404, "Kriteria tidak ditemukan")
    return {"status": "deleted"}


@api.patch("/jobs/{job_id}/education")
async def update_education(
    job_id: str,
    payload: EducationUpdate,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    update: dict = {}
    if payload.education_level is not None:
        update["education_level"] = payload.education_level.strip()
    if payload.education_major is not None:
        update["education_major"] = payload.education_major.strip()
    if payload.edu_level_pct is not None or payload.edu_major_pct is not None:
        lvl = payload.edu_level_pct if payload.edu_level_pct is not None else 70
        maj = payload.edu_major_pct if payload.edu_major_pct is not None else 100 - lvl
        if lvl < 0 or maj < 0 or (lvl + maj) != 100:
            raise HTTPException(400, "Bobot jenjang + jurusan harus berjumlah 100")
        update["weights.edu_level_pct"] = lvl
        update["weights.edu_major_pct"] = maj
    # Refresh aggregate education_requirement string for legacy compat
    if "education_level" in update or "education_major" in update:
        job = await db.job_postings.find_one({"id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "JD tidak ditemukan")
        lvl = update.get("education_level", job.get("education_level", ""))
        maj = update.get("education_major", job.get("education_major", ""))
        update["education_requirement"] = (
            f"{lvl} - {maj}" if lvl and maj and maj.lower() not in ("semua jurusan", "") else (lvl or maj or "")
        )
    res = await db.job_postings.update_one({"id": job_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "JD tidak ditemukan")
    return await db.job_postings.find_one({"id": job_id}, {"_id": 0})


# ============ CANDIDATES + SCREENING ============
async def _screen_candidate_for_job(
    candidate_id: str, job_id: str, parsed: dict, cfg: Optional[dict] = None
) -> Optional[str]:
    """Run semantic matching for one candidate against one job and persist result."""
    import uuid

    job = await db.job_postings.find_one({"id": job_id})
    if not job:
        return None
    if cfg is None:
        cfg = await _get_ai_config_for_task("scoring")
    weights = job.get("weights", {})
    jd_data = {
        "target_position": job.get("target_position", ""),
        "department": job.get("department", ""),
        "min_experience_years": job.get("min_experience_years", 0),
        "education_requirement": job.get("education_requirement", ""),
        "education_level": job.get("education_level", ""),
        "education_major": job.get("education_major", ""),
        "edu_level_pct": weights.get("edu_level_pct", 70),
        "edu_major_pct": weights.get("edu_major_pct", 30),
        "responsibilities": job.get("responsibilities", []),
        "must_have": [
            {"value": c["value"], "weight": c.get("weight", 3)}
            for c in job.get("criteria", []) if c["type"] == "must"
        ],
        "nice_to_have": [
            {"value": c["value"], "weight": c.get("weight", 3)}
            for c in job.get("criteria", []) if c["type"] == "nice"
        ],
    }
    evaluation = await evaluate_match(jd_data, parsed, cfg)
    total = calculate_total_score(evaluation, weights)
    recommendation = recommendation_from_score(total, weights)

    sr_id = str(uuid.uuid4())
    sr = {
        "id": sr_id,
        "job_posting_id": job_id,
        "candidate_id": candidate_id,
        "total_score": total,
        "must_have": evaluation["must_have"],
        "experience": evaluation["experience"],
        "domain": evaluation["domain"],
        "education": evaluation["education"],
        "nice_have": evaluation["nice_have"],
        "recommendation": recommendation,
        "rationale_summary": evaluation["rationale_summary"],
        "strengths": evaluation["strengths"],
        "gaps_summary": evaluation["gaps_summary"],
        "decision": "pending",
        "decided_by": None,
        "decided_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.screening_results.insert_one(sr)
    return sr_id


async def _process_candidate(candidate_id: str, job_id: str) -> None:
    """Background task: parse CV + evaluate against JD."""
    try:
        cand = await db.candidates.find_one({"id": candidate_id})
        if not cand:
            return
        parsing_cfg = await _get_ai_config_for_task("parsing")
        scoring_cfg = await _get_ai_config_for_task("scoring")
        await db.candidates.update_one({"id": candidate_id}, {"$set": {"status": "processing"}})
        parsed = await parse_cv(cand["raw_text"], parsing_cfg)
        await db.candidates.update_one(
            {"id": candidate_id},
            {
                "$set": {
                    "name": parsed.get("name") or cand.get("name", "Unknown"),
                    "email": parsed.get("email", ""),
                    "phone": parsed.get("phone", ""),
                    "parsed": parsed,
                    "status": "parsed",
                }
            },
        )
        await _screen_candidate_for_job(candidate_id, job_id, parsed, scoring_cfg)
    except Exception as e:
        logger.exception("Candidate processing failed")
        await db.candidates.update_one(
            {"id": candidate_id},
            {"$set": {"status": "failed", "error_message": str(e)}},
        )


async def _rescreen_pool_candidate(candidate_id: str, job_id: str) -> None:
    """Background task: rescreen an already-parsed candidate against another job."""
    try:
        cand = await db.candidates.find_one({"id": candidate_id})
        if not cand or cand.get("status") != "parsed":
            return
        # skip if already screened for this job
        exists = await db.screening_results.find_one(
            {"candidate_id": candidate_id, "job_posting_id": job_id}
        )
        if exists:
            return
        scoring_cfg = await _get_ai_config_for_task("scoring")
        await _screen_candidate_for_job(candidate_id, job_id, cand.get("parsed", {}), scoring_cfg)
    except Exception:
        logger.exception("Rescreen failed for candidate %s", candidate_id)


@api.post("/jobs/{job_id}/upload-cv")
async def upload_cv(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    job = await db.job_postings.find_one({"id": job_id})
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")
    if len(files) > 500:
        raise HTTPException(400, "Maksimum 500 CV per sesi")

    import uuid

    created_ids: list[str] = []
    for f in files:
        content = await f.read()
        text = extract_text(f.filename or "cv.txt", content)
        cid = str(uuid.uuid4())
        doc = {
            "id": cid,
            "name": "Memproses...",
            "email": "",
            "phone": "",
            "file_name": f.filename,
            "raw_text": text,
            "parsed": {},
            "status": "pending",
            "error_message": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "job_posting_id": job_id,
        }
        await db.candidates.insert_one(doc)
        created_ids.append(cid)
        background_tasks.add_task(_process_candidate, cid, job_id)

    return {"uploaded": len(created_ids), "candidate_ids": created_ids}


@api.get("/jobs/{job_id}/candidates")
async def list_job_candidates(
    job_id: str, user: dict = Depends(get_current_user)
) -> list[dict]:
    """Return ranked list of screening results joined with candidate info."""
    results = await db.screening_results.find({"job_posting_id": job_id}, {"_id": 0}).to_list(1000)
    # also include candidates still processing
    candidates = await db.candidates.find({"job_posting_id": job_id}, {"_id": 0}).to_list(1000)
    cand_map = {c["id"]: c for c in candidates}
    scored_ids = {r["candidate_id"] for r in results}

    out = []
    for r in results:
        c = cand_map.get(r["candidate_id"], {})
        out.append(
            {
                **r,
                "candidate_name": c.get("name", "Unknown"),
                "candidate_email": c.get("email", ""),
                "candidate_status": c.get("status", "parsed"),
            }
        )
    out.sort(key=lambda x: x["total_score"], reverse=True)

    # pending (no screening yet)
    for c in candidates:
        if c["id"] not in scored_ids:
            out.append(
                {
                    "id": None,
                    "job_posting_id": job_id,
                    "candidate_id": c["id"],
                    "candidate_name": c.get("name", "Memproses..."),
                    "candidate_email": c.get("email", ""),
                    "candidate_status": c.get("status", "pending"),
                    "total_score": 0,
                    "recommendation": "pending",
                    "decision": "pending",
                    "rationale_summary": "",
                    "created_at": c["created_at"],
                }
            )
    return out


@api.get("/screenings/{screening_id}")
async def get_screening(screening_id: str, user: dict = Depends(get_current_user)) -> dict:
    sr = await db.screening_results.find_one({"id": screening_id}, {"_id": 0})
    if not sr:
        raise HTTPException(404, "Hasil screening tidak ditemukan")
    cand = await db.candidates.find_one({"id": sr["candidate_id"]}, {"_id": 0})
    job = await db.job_postings.find_one({"id": sr["job_posting_id"]}, {"_id": 0})
    return {"screening": sr, "candidate": cand, "job": job}


# ============ TALENT POOL ============
@api.get("/talent-pool")
async def list_talent_pool(user: dict = Depends(get_current_user)) -> list[dict]:
    """Return all parsed candidates with their best score across all jobs."""
    candidates = await db.candidates.find(
        {"status": "parsed"}, {"_id": 0, "raw_text": 0}
    ).to_list(2000)

    # Aggregate best score per candidate
    pipeline = [
        {
            "$group": {
                "_id": "$candidate_id",
                "best_score": {"$max": "$total_score"},
                "screenings_count": {"$sum": 1},
                "shortlisted_count": {
                    "$sum": {"$cond": [{"$eq": ["$decision", "shortlisted"]}, 1, 0]}
                },
            }
        }
    ]
    agg = await db.screening_results.aggregate(pipeline).to_list(5000)
    stats = {row["_id"]: row for row in agg}

    out = []
    for c in candidates:
        s = stats.get(c["id"], {})
        parsed = c.get("parsed", {}) or {}
        out.append(
            {
                "id": c["id"],
                "name": c.get("name", "Unknown"),
                "email": c.get("email", ""),
                "phone": c.get("phone", ""),
                "years_of_experience": parsed.get("years_of_experience", 0),
                "top_skills": (parsed.get("skills", []) or [])[:6],
                "current_position": (parsed.get("work_history", [{}]) or [{}])[0].get("position", "")
                if parsed.get("work_history")
                else "",
                "best_score": s.get("best_score", 0),
                "screenings_count": s.get("screenings_count", 0),
                "shortlisted_count": s.get("shortlisted_count", 0),
                "created_at": c.get("created_at", ""),
            }
        )
    out.sort(key=lambda x: (x["best_score"], x["screenings_count"]), reverse=True)
    return out


@api.get("/talent-pool/{candidate_id}")
async def get_pool_candidate(
    candidate_id: str, user: dict = Depends(get_current_user)
) -> dict:
    """Get candidate detail + all screenings across jobs."""
    cand = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "raw_text": 0})
    if not cand:
        raise HTTPException(404, "Kandidat tidak ditemukan")
    screenings = await db.screening_results.find(
        {"candidate_id": candidate_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    # attach job titles
    job_ids = list({s["job_posting_id"] for s in screenings})
    jobs = await db.job_postings.find(
        {"id": {"$in": job_ids}}, {"_id": 0, "id": 1, "title": 1, "department": 1}
    ).to_list(200)
    job_map = {j["id"]: j for j in jobs}
    for s in screenings:
        j = job_map.get(s["job_posting_id"], {})
        s["job_title"] = j.get("title", "—")
        s["job_department"] = j.get("department", "")
    return {"candidate": cand, "screenings": screenings}


class ScreenFromPoolRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    auto_top_n: int = 0  # if > 0, ignore candidate_ids and pick top-N from pool not yet screened


@api.post("/jobs/{job_id}/screen-from-pool")
async def screen_from_pool(
    job_id: str,
    payload: ScreenFromPoolRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("hr_recruiter", "admin_it")),
) -> dict:
    job = await db.job_postings.find_one({"id": job_id})
    if not job:
        raise HTTPException(404, "JD tidak ditemukan")

    already = {
        s["candidate_id"]
        async for s in db.screening_results.find(
            {"job_posting_id": job_id}, {"candidate_id": 1, "_id": 0}
        )
    }

    if payload.auto_top_n and payload.auto_top_n > 0:
        # pick top-N candidates from pool (by best historical score) not yet screened for this job
        pipeline = [
            {
                "$group": {
                    "_id": "$candidate_id",
                    "best_score": {"$max": "$total_score"},
                }
            },
            {"$sort": {"best_score": -1}},
        ]
        agg = await db.screening_results.aggregate(pipeline).to_list(2000)
        top_ids = [row["_id"] for row in agg if row["_id"] not in already][: payload.auto_top_n]
        # also include parsed candidates with no screenings yet
        if len(top_ids) < payload.auto_top_n:
            extra = await db.candidates.find(
                {"status": "parsed", "id": {"$nin": list(already) + top_ids}},
                {"id": 1, "_id": 0},
            ).limit(payload.auto_top_n - len(top_ids)).to_list(payload.auto_top_n)
            top_ids.extend([e["id"] for e in extra])
        target_ids = top_ids
    else:
        target_ids = [cid for cid in payload.candidate_ids if cid not in already]

    queued = 0
    for cid in target_ids:
        cand = await db.candidates.find_one({"id": cid}, {"_id": 0, "status": 1})
        if not cand or cand.get("status") != "parsed":
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
) -> dict:
    if payload.decision not in ("shortlisted", "rejected", "hold", "pending"):
        raise HTTPException(400, "Keputusan tidak valid")
    res = await db.screening_results.find_one_and_update(
        {"id": screening_id},
        {
            "$set": {
                "decision": payload.decision,
                "decided_by": user["id"],
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )
    if not res:
        raise HTTPException(404, "Hasil screening tidak ditemukan")
    return _clean(res)


# ============ AI PROVIDER CONFIG ============
@api.get("/config/ai-providers")
async def list_providers(user: dict = Depends(require_roles("admin_it"))) -> list[dict]:
    docs = await db.ai_provider_configs.find({}, {"_id": 0}).to_list(50)
    for d in docs:
        if d.get("api_key"):
            d["api_key"] = "***" + d["api_key"][-4:] if len(d["api_key"]) > 4 else "***"
    return docs


@api.patch("/config/ai-providers/{cfg_id}")
async def update_provider(
    cfg_id: str,
    payload: AIProviderUpdate,
    user: dict = Depends(require_roles("admin_it")),
) -> dict:
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    # If activating this one, deactivate others
    if update.get("is_active"):
        await db.ai_provider_configs.update_many(
            {"id": {"$ne": cfg_id}}, {"$set": {"is_active": False}}
        )
    res = await db.ai_provider_configs.find_one_and_update(
        {"id": cfg_id}, {"$set": update}, return_document=True
    )
    if not res:
        raise HTTPException(404, "Konfigurasi tidak ditemukan")
    res = _clean(res)
    if res.get("api_key"):
        res["api_key"] = "***" + res["api_key"][-4:] if len(res["api_key"]) > 4 else "***"
    return res


@api.post("/config/ai-providers")
async def create_provider(
    payload: AIProviderUpdate, user: dict = Depends(require_roles("admin_it"))
) -> dict:
    import uuid

    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name or "Custom Provider",
        "provider_type": payload.provider_type or "custom",
        "base_url": payload.base_url or "",
        "api_key": payload.api_key or "",
        "llm_provider": payload.llm_provider or "openai",
        "model_name": payload.model_name or "gpt-4o-mini",
        "temperature": payload.temperature if payload.temperature is not None else 0.2,
        "max_tokens": payload.max_tokens or 4000,
        "is_active": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_provider_configs.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    if out.get("api_key"):
        out["api_key"] = "***" + out["api_key"][-4:] if len(out["api_key"]) > 4 else "***"
    return out


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


# ============ TASK MODEL ASSIGNMENTS ============
class TaskAssignmentUpdate(BaseModel):
    parsing_provider_id: Optional[str] = None
    scoring_provider_id: Optional[str] = None


@api.get("/config/task-assignments")
async def get_task_assignments(user: dict = Depends(require_roles("admin_it"))) -> dict:
    settings = await db.system_settings.find_one(
        {"id": "task_assignments"}, {"_id": 0}
    ) or {"id": "task_assignments", "parsing_provider_id": None, "scoring_provider_id": None}

    async def _resolve(pid: Optional[str]) -> Optional[dict]:
        if not pid:
            return None
        p = await db.ai_provider_configs.find_one({"id": pid}, {"_id": 0})
        if p and p.get("api_key"):
            p["api_key"] = "***" + p["api_key"][-4:] if len(p["api_key"]) > 4 else "***"
        return p

    return {
        "parsing_provider_id": settings.get("parsing_provider_id"),
        "scoring_provider_id": settings.get("scoring_provider_id"),
        "parsing_provider": await _resolve(settings.get("parsing_provider_id")),
        "scoring_provider": await _resolve(settings.get("scoring_provider_id")),
    }


@api.put("/config/task-assignments")
async def update_task_assignments(
    payload: TaskAssignmentUpdate,
    user: dict = Depends(require_roles("admin_it")),
) -> dict:
    update: dict = {"id": "task_assignments"}
    # Validate provider IDs exist (if provided non-empty)
    for field in ("parsing_provider_id", "scoring_provider_id"):
        val = getattr(payload, field)
        if val:
            exists = await db.ai_provider_configs.find_one({"id": val})
            if not exists:
                raise HTTPException(400, f"Provider untuk {field} tidak ditemukan")
            update[field] = val
        else:
            update[field] = None
    await db.system_settings.update_one(
        {"id": "task_assignments"}, {"$set": update}, upsert=True
    )
    return {"status": "saved", **update}


# ============ DASHBOARD ============
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)) -> dict:
    active_jobs = await db.job_postings.count_documents({"status": "active"})
    total_jobs = await db.job_postings.count_documents({})
    total_candidates = await db.candidates.count_documents({})
    total_screenings = await db.screening_results.count_documents({})

    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    processed_today = await db.candidates.count_documents(
        {"created_at": {"$regex": f"^{today_iso}"}}
    )

    # Score distribution
    pipeline = [
        {
            "$bucket": {
                "groupBy": "$total_score",
                "boundaries": [0, 40, 75, 101],
                "default": "other",
                "output": {"count": {"$sum": 1}},
            }
        }
    ]
    dist_raw = await db.screening_results.aggregate(pipeline).to_list(10)
    dist = {"low": 0, "mid": 0, "high": 0}
    for b in dist_raw:
        if b["_id"] == 0:
            dist["low"] = b["count"]
        elif b["_id"] == 40:
            dist["mid"] = b["count"]
        elif b["_id"] == 75:
            dist["high"] = b["count"]

    recent_jobs = await db.job_postings.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)

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
