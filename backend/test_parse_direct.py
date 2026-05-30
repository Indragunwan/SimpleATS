import asyncio
import traceback
from sqlalchemy import select
from server import async_session, _process_candidate, DBCandidate

async def main():
    candidate_id = "babd6a58-6a74-4214-b483-80dbc97ff8cd"
    job_id = "2912b98b-12c8-4cf4-b16c-54987c44eab6"
    print(f"Running direct processing for candidate {candidate_id}...")
    try:
        await _process_candidate(candidate_id, job_id)
        
        async with async_session() as session:
            stmt = select(DBCandidate).where(DBCandidate.id == candidate_id)
            res = await session.execute(stmt)
            cand = res.scalar_one_or_none()
            print("Status after processing:", cand.status)
            print("Error message in DB:", repr(cand.error_message))
    except Exception as e:
        print("Caught exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
