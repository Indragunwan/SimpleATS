"""Idempotent seeding for demo users and default AI provider config."""
import logging
from datetime import datetime, timezone

from auth import hash_password

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
        "email": "admin@demo.com",
        "password": "demo123",
        "role": "admin_it",
    },
]


async def seed_demo_users(db) -> None:
    import uuid

    for user in DEMO_USERS:
        existing = await db.users.find_one({"email": user["email"]})
        if existing:
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "name": user["name"],
            "email": user["email"],
            "password_hash": hash_password(user["password"]),
            "role": user["role"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        logger.info(f"Seeded demo user: {user['email']}")


async def seed_default_ai_config(db) -> None:
    import uuid

    existing = await db.ai_provider_configs.find_one({"provider_type": "emergent"})
    if existing:
        return
    doc = {
        "id": str(uuid.uuid4()),
        "name": "Emergent Universal (Default)",
        "provider_type": "emergent",
        "base_url": "",
        "api_key": "",
        "llm_provider": "anthropic",
        "model_name": "claude-sonnet-4-6",
        "temperature": 0.2,
        "max_tokens": 4000,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_provider_configs.insert_one(doc)
    logger.info("Seeded default AI provider config (Emergent)")


async def backfill_criteria_ids(db) -> None:
    """Backfill missing id/weight fields on existing job criteria for backward compat."""
    import uuid

    updated = 0
    async for job in db.job_postings.find({}, {"_id": 0, "id": 1, "criteria": 1}):
        criteria = job.get("criteria") or []
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
            await db.job_postings.update_one(
                {"id": job["id"]}, {"$set": {"criteria": criteria}}
            )
            updated += 1
    if updated:
        logger.info(f"Backfilled criteria id/weight on {updated} job(s)")
