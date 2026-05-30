import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from backend.server import _process_candidate, DATABASE_URL, DBCandidate

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Let's find the latest failed candidate
    async with async_session() as session:
        stmt = select(DBCandidate).where(DBCandidate.status == "failed").order_by(DBCandidate.created_at.desc()).limit(1)
        res = await session.execute(stmt)
        cand = res.scalar_one_or_none()
        if not cand:
            print("No failed candidate found.")
            return
        
        print(f"Re-running candidate {cand.id} ({cand.file_name})...")
        # Run the process directly to catch the exception traceback
        from backend.server import _get_ai_config_for_task
        from backend.ai_service import parse_cv, evaluate_match
        
        parsing_cfg = await _get_ai_config_for_task(session, "parsing")
        scoring_cfg = await _get_ai_config_for_task(session, "scoring")
        
        try:
            print("1. Parsing CV...")
            parsed = await parse_cv(cand.raw_text, parsing_cfg)
            print("Parsed CV successfully:", parsed.keys())
            
            print("2. Screening candidate...")
            from backend.server import _screen_candidate_for_job
            # We don't have the job_posting_id, let's get it from the candidate
            job_id = cand.job_posting_id
            print(f"Job posting ID: {job_id}")
            
            await _screen_candidate_for_job(session, cand.id, job_id, parsed, scoring_cfg)
            print("Screened candidate successfully!")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
