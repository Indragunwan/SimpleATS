import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('mysql+aiomysql://root:@localhost/simple_ats')
    async with engine.connect() as conn:
        print("--- CANDIDATES ---")
        res = await conn.execute(text("SELECT id, name, status, error_message, created_at FROM candidates ORDER BY created_at DESC LIMIT 5"))
        for r in res.fetchall():
            print(r)
            
        print("--- SCREENING RESULTS ---")
        res2 = await conn.execute(text("SELECT id, job_posting_id, candidate_id, total_score, created_at FROM screening_results ORDER BY created_at DESC LIMIT 5"))
        for r in res2.fetchall():
            print(r)

if __name__ == "__main__":
    asyncio.run(main())
