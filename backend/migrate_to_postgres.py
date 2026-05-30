import sys
import os
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

# Adjust path to find backend modules
sys.path.append(str(Path(__file__).parent))

from models import (
    Base,
    DBUser,
    DBJobPosting,
    DBCandidate,
    DBScreeningResult,
    DBAIProviderConfig,
    DBSystemSettings
)

# Config
MYSQL_URL = "mysql+aiomysql://root:@localhost/simple_ats"

if len(sys.argv) < 2:
    print("USAGE: python migrate_to_postgres.py <postgres_password>")
    sys.exit(1)

pg_password = sys.argv[1]
POSTGRES_URL = f"postgresql+asyncpg://postgres:{pg_password}@localhost:5432/simple_ats"

async def create_database_if_not_exists():
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password=pg_password,
            host="localhost",
            port="5432"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'simple_ats';")
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("CREATE DATABASE simple_ats;")
            print("Database 'simple_ats' created successfully in PostgreSQL.")
        else:
            print("Database 'simple_ats' already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error creating PostgreSQL database: {e}")
        sys.exit(1)

async def main():
    await create_database_if_not_exists()
    
    # Engines
    mysql_engine = create_async_engine(MYSQL_URL, echo=False)
    pg_engine = create_async_engine(POSTGRES_URL, echo=False)
    
    mysql_session = async_sessionmaker(mysql_engine, class_=AsyncSession, expire_on_commit=False)
    pg_session = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)
    
    print("Connecting to PostgreSQL and creating tables...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully.")
    
    async with mysql_session() as my_sess, pg_session() as pg_sess:
        # 1. Migrate AI Provider Configs
        print("Migrating AI Provider Configs...")
        res = await my_sess.execute(select(DBAIProviderConfig))
        configs = res.scalars().all()
        for c in configs:
            new_c = DBAIProviderConfig(
                id=c.id,
                name=c.name,
                provider_type=c.provider_type,
                base_url=c.base_url,
                api_key=c.api_key,
                llm_provider=c.llm_provider,
                model_name=c.model_name,
                temperature=c.temperature,
                max_tokens=c.max_tokens,
                is_active=c.is_active,
                created_at=c.created_at
            )
            pg_sess.add(new_c)
            
        # 2. Migrate System Settings
        print("Migrating System Settings...")
        res = await my_sess.execute(select(DBSystemSettings))
        settings = res.scalars().all()
        for s in settings:
            new_s = DBSystemSettings(
                id=s.id,
                parsing_provider_id=s.parsing_provider_id,
                scoring_provider_id=s.scoring_provider_id
            )
            pg_sess.add(new_s)
            
        # 3. Migrate Users
        print("Migrating Users...")
        res = await my_sess.execute(select(DBUser))
        users = res.scalars().all()
        for u in users:
            new_u = DBUser(
                id=u.id,
                name=u.name,
                email=u.email,
                password_hash=u.password_hash,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at
            )
            pg_sess.add(new_u)
            
        # 4. Migrate Job Postings
        print("Migrating Job Postings...")
        res = await my_sess.execute(select(DBJobPosting))
        jobs = res.scalars().all()
        for j in jobs:
            new_j = DBJobPosting(
                id=j.id,
                title=j.title,
                department=j.department,
                raw_jd_text=j.raw_jd_text,
                file_name=j.file_name,
                target_position=j.target_position,
                min_experience_years=j.min_experience_years,
                responsibilities=j.responsibilities,
                criteria=j.criteria,
                weights=j.weights,
                status=j.status,
                created_by=j.created_by,
                created_at=j.created_at,
                extraction_status=j.extraction_status,
                extraction_error=j.extraction_error,
                start_date=j.start_date,
                end_date=j.end_date,
                location=j.location
            )
            pg_sess.add(new_j)
            
        # 5. Migrate Candidates
        print("Migrating Candidates...")
        res = await my_sess.execute(select(DBCandidate))
        candidates = res.scalars().all()
        for c in candidates:
            new_c = DBCandidate(
                id=c.id,
                name=c.name,
                email=c.email,
                phone=c.phone,
                file_name=c.file_name,
                raw_text=c.raw_text,
                parsed=c.parsed,
                status=c.status,
                error_message=c.error_message,
                created_at=c.created_at,
                job_posting_id=c.job_posting_id
            )
            pg_sess.add(new_c)
            
        # 6. Migrate Screening Results
        print("Migrating Screening Results...")
        res = await my_sess.execute(select(DBScreeningResult))
        results = res.scalars().all()
        for r in results:
            new_r = DBScreeningResult(
                id=r.id,
                job_posting_id=r.job_posting_id,
                candidate_id=r.candidate_id,
                total_score=r.total_score,
                must_have=r.must_have,
                experience=r.experience,
                domain=r.domain,
                education=r.education,
                nice_have=r.nice_have,
                recommendation=r.recommendation,
                rationale_summary=r.rationale_summary,
                strengths=r.strengths,
                gaps_summary=r.gaps_summary,
                decision=r.decision,
                decided_by=r.decided_by,
                decided_at=r.decided_at,
                created_at=r.created_at,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
                total_tokens=r.total_tokens
            )
            pg_sess.add(new_r)
            
        print("Saving changes to PostgreSQL...")
        await pg_sess.commit()
        print("Migration completed successfully!")

if __name__ == '__main__':
    asyncio.run(main())
