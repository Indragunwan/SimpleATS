with open('backend/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

rescreen_all_api = """@api.post("/jobs/{job_id}/candidates/rescreen-all")
async def rescreen_all_candidates(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("hr_recruiter", "hiring_manager", "admin_it")),
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


@api.post("/jobs/{job_id}/candidates/{candidate_id}/rescreen")"""

if '/candidates/rescreen-all' not in text:
    text = text.replace(
        '@api.post("/jobs/{job_id}/candidates/{candidate_id}/rescreen")',
        rescreen_all_api
    )

with open('backend/server.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("backend/server.py patched with rescreen-all API.")
