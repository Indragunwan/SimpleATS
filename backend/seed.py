"""Idempotent seeding for demo users and default AI provider config."""
import logging
from datetime import datetime, timezone

from auth import hash_password
from models import DBUser, DBAIProviderConfig, DBJobPosting
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "name": "Hana Recruiter",
        "email": "hr@demo.com",
        "password": "demo123",
        "role": "hr_recruiter",
    },
    {
        "name": "Manuel Manager",
        "email": "manager@demo.com",
        "password": "demo123",
        "role": "hiring_manager",
    },
    {
        "name": "Adi Admin",
        "email": "hrdaplzoommeeting@gmail.com",
        "password": "demo123",
        "role": "admin_it",
    },
]


async def seed_demo_users(session) -> None:
    import uuid

    for user in DEMO_USERS:
        stmt = select(DBUser).where(DBUser.email == user["email"])
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            continue
        db_user = DBUser(
            id=str(uuid.uuid4()),
            name=user["name"],
            email=user["email"],
            password_hash=hash_password(user["password"]),
            role=user["role"],
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(db_user)
        logger.info(f"Seeded demo user: {user['email']}")
    await session.commit()


async def seed_default_ai_config(session) -> None:
    import uuid

    stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.provider_type == "emergent")
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return
    doc = DBAIProviderConfig(
        id=str(uuid.uuid4()),
        name="Emergent Universal (Default)",
        provider_type="emergent",
        base_url="",
        api_key="",
        llm_provider="anthropic",
        model_name="claude-sonnet-4-6",
        temperature=0.2,
        max_tokens=4000,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(doc)
    await session.commit()
    logger.info("Seeded default AI provider config (Emergent)")


async def backfill_criteria_ids(session) -> None:
    """Backfill missing id/weight fields on existing job criteria for backward compat."""
    import uuid

    stmt = select(DBJobPosting)
    res = await session.execute(stmt)
    jobs = res.scalars().all()
    updated = 0
    for job in jobs:
        criteria = job.criteria or []
        if not criteria:
            continue
        changed = False
        for c in criteria:
            if "id" not in c or not c["id"]:
                c["id"] = str(uuid.uuid4())
                changed = True
            if "weight" not in c:
                c["weight"] = 3
                changed = True
        if changed:
            job.criteria = criteria
            flag_modified(job, "criteria")
            updated += 1
    if updated:
        await session.commit()
        logger.info(f"Backfilled criteria id/weight on {updated} job(s)")
