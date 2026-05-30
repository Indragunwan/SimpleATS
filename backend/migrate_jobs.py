import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('mysql+aiomysql://root:@localhost/simple_ats')
    async with engine.connect() as conn:
        print("Running database migration...")
        
        # Check columns
        res = await conn.execute(text("SHOW COLUMNS FROM job_postings"))
        columns = [r[0] for r in res.fetchall()]
        
        if "start_date" not in columns:
            await conn.execute(text("ALTER TABLE job_postings ADD COLUMN start_date VARCHAR(50) NULL"))
            print("Added start_date column.")
        else:
            print("start_date already exists.")
            
        if "end_date" not in columns:
            await conn.execute(text("ALTER TABLE job_postings ADD COLUMN end_date VARCHAR(50) NULL"))
            print("Added end_date column.")
        else:
            print("end_date already exists.")
            
        if "location" not in columns:
            await conn.execute(text("ALTER TABLE job_postings ADD COLUMN location VARCHAR(255) NULL"))
            print("Added location column.")
        else:
            print("location already exists.")
            
        await conn.commit()
        print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
