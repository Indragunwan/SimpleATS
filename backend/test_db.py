import asyncio
from server import async_session
from sqlalchemy import select, desc
from models import DBJobPosting

async def main():
    async with async_session() as s:
        res = await s.execute(select(DBJobPosting).order_by(desc(DBJobPosting.created_at)).limit(1))
        j = res.scalars().first()
        print('status:', j.extraction_status)
        print('error:', j.extraction_error)

asyncio.run(main())
