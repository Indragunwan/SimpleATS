with open('backend/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Helper search text builder
search_text_helper = """def _build_cv_search_text(cand_name: str, parsed: dict) -> str:
    summary = parsed.get("summary") or ""
    skills = ", ".join(parsed.get("skills", []) or [])
    hard_skills = ", ".join(parsed.get("hard_skills", []) or [])
    soft_skills = ", ".join(parsed.get("soft_skills", []) or [])
    
    edu_list = []
    for edu in parsed.get("education", []) or []:
        degree = edu.get("degree") or ""
        inst = edu.get("institution") or ""
        edu_list.append(f"{degree} di {inst}")
    edu_str = ", ".join(edu_list)
    
    work_list = []
    for w in parsed.get("work_history", []) or []:
        pos = w.get("position") or ""
        comp = w.get("company") or ""
        work_list.append(f"{pos} di {comp}")
    work_str = ", ".join(work_list)
    
    parts = []
    if cand_name: parts.append(f"Nama: {cand_name}")
    if summary: parts.append(f"Ringkasan: {summary}")
    if skills: parts.append(f"Keahlian: {skills}")
    if hard_skills: parts.append(f"Keahlian Teknis: {hard_skills}")
    if soft_skills: parts.append(f"Keahlian Non-Teknis: {soft_skills}")
    if edu_str: parts.append(f"Pendidikan: {edu_str}")
    if work_str: parts.append(f"Pengalaman Kerja: {work_str}")
    
    return "\\n".join(parts)


async def _process_candidate(candidate_id: str, job_id: str) -> None:"""

if 'def _build_cv_search_text' not in text:
    text = text.replace(
        'async def _process_candidate(candidate_id: str, job_id: str) -> None:',
        search_text_helper
    )

# Embedding generator call inside _process_candidate
old_process_save = """                parsed = await parse_cv(cand.raw_text, parsing_cfg)
                cand.name = parsed.get("name") or cand.name or "Unknown"
                cand.email = parsed.get("email", "")
                cand.phone = parsed.get("phone", "")
                cand.parsed = parsed
                cand.status = "parsed"
                await session.commit()"""

new_process_save = """                parsed = await parse_cv(cand.raw_text, parsing_cfg)
                cand.name = parsed.get("name") or cand.name or "Unknown"
                cand.email = parsed.get("email", "")
                cand.phone = parsed.get("phone", "")
                cand.parsed = parsed
                cand.status = "parsed"
                
                # Generate cv_embedding
                try:
                    from ai_service import generate_embedding
                    search_text = _build_cv_search_text(cand.name, parsed)
                    cand.cv_embedding = await generate_embedding(search_text, parsing_cfg)
                except Exception as emb_err:
                    logger.error(f"Gagal generate embedding untuk kandidat {candidate_id}: {emb_err}")
                
                await session.commit()"""

if 'cand.cv_embedding = await generate_embedding' not in text:
    text = text.replace(old_process_save, new_process_save)

# Add POST /talent-pool/search endpoint
search_endpoint = """# ============ TALENT POOL ============
@api.post("/talent-pool/search")
async def search_talent_pool(
    payload: dict,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query pencarian tidak boleh kosong")
        
    scoring_cfg = await _get_ai_config_for_task(session, "scoring")
    
    try:
        from ai_service import generate_embedding
        query_embedding = await generate_embedding(query, scoring_cfg)
    except Exception as e:
        logger.error(f"Gagal generate embedding untuk search query: {e}")
        raise HTTPException(500, f"Gagal memproses pencarian semantik: {str(e)}")
        
    # Get all parsed candidates that have embeddings
    stmt_c = select(DBCandidate).where(
        and_(
            DBCandidate.status == "parsed",
            DBCandidate.cv_embedding.isnot(None)
        )
    )
    res_c = await session.execute(stmt_c)
    candidates = res_c.scalars().all()
    
    # Get stats
    stmt_stats = select(
        DBScreeningResult.candidate_id,
        func.max(DBScreeningResult.total_score).label("best_score"),
        func.count(DBScreeningResult.id).label("screenings_count"),
        func.sum(
            case(
                (DBScreeningResult.decision == "shortlisted", 1),
                else_=0
            )
        ).label("shortlisted_count")
    ).group_by(DBScreeningResult.candidate_id)
    res_stats = await session.execute(stmt_stats)
    stats_rows = res_stats.all()
    stats = {}
    for row in stats_rows:
        stats[row.candidate_id] = {
            "best_score": row.best_score or 0,
            "screenings_count": row.screenings_count or 0,
            "shortlisted_count": int(row.shortlisted_count or 0),
        }
        
    import numpy as np
    q_vec = np.array(query_embedding)
    q_norm = np.linalg.norm(q_vec)
    
    if q_norm == 0:
        raise HTTPException(500, "AI Provider mengembalikan vektor kosong untuk query ini.")
        
    out = []
    for c in candidates:
        if not c.cv_embedding or len(c.cv_embedding) != len(query_embedding):
            continue
            
        c_vec = np.array(c.cv_embedding)
        c_norm = np.linalg.norm(c_vec)
        if c_norm == 0:
            continue
            
        score = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
        pct_score = max(0.0, min(100.0, (score + 1.0) / 2.0 * 100.0))
        
        s = stats.get(c.id, {})
        parsed = _ensure_dict(c.parsed)
        work_history = parsed.get("work_history", [])
        current_position = ""
        if work_history and isinstance(work_history, list) and len(work_history) > 0:
            if isinstance(work_history[0], dict):
                current_position = work_history[0].get("position", "")
                
        out.append({
            "id": c.id,
            "name": c.name or "Unknown",
            "email": c.email or "",
            "phone": c.phone or "",
            "years_of_experience": parsed.get("years_of_experience", 0),
            "top_skills": (parsed.get("skills", []) or [])[:6],
            "current_position": current_position,
            "best_score": s.get("best_score", 0),
            "screenings_count": s.get("screenings_count", 0),
            "shortlisted_count": s.get("shortlisted_count", 0),
            "created_at": c.created_at,
            "similarity_score": round(pct_score, 2)
        })
        
    # Sort by similarity score descending
    out.sort(key=lambda x: x["similarity_score"], reverse=True)
    return out


@api.get("/talent-pool")"""

if '/talent-pool/search' not in text:
    text = text.replace(
        '# ============ TALENT POOL ============\n@api.get("/talent-pool")',
        search_endpoint
    )

with open('backend/server.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("backend/server.py patched with semantic search API.")
