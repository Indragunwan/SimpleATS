"""AI Service: JD extraction, CV parsing, semantic matching, rationale generation."""
import json
import logging
import os
import re
import uuid
from typing import Any, Optional

# Note: emergentintegrations import removed to allow using other LLM providers.
# The call_llm function below is pluggable — provide an async `llm_client` in
# the `config` dict (callable) that accepts (system_message, user_message, config)
# and returns a string response. Example: `config['llm_client'] = my_async_callable`.

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


def _extract_json(text: str) -> Optional[dict]:
    """Robustly extract JSON object from LLM response."""
    if not text:
        return None
    # Try direct parse
    text = text.strip()
    if text.startswith("```"):
        # strip code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to find first JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


async def call_llm(
    system_message: str,
    user_message: str,
    config: Optional[dict] = None,
    session_id: Optional[str] = None,
) -> str:
    """Pluggable LLM caller.

    To use an LLM, provide `config['llm_client']` as an async callable with
    signature `(system_message, user_message, config) -> str`.
    """
    config = config or {}

    llm_client = config.get("llm_client")
    if llm_client and callable(llm_client):
        # Expecting an async callable
        resp = llm_client(system_message, user_message, config)
        if hasattr(resp, "__await__"):
            resp = await resp
        return resp if isinstance(resp, str) else str(resp)

    # Fallback to default LLM client
    provider_type = config.get("provider_type", "emergent")
    
    if provider_type == "emergent":
        # Default emergent provider uses Nvidia NIM API if key is available
        nv_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY")
        if nv_key:
            api_key = nv_key
            base_url = "https://integrate.api.nvidia.com/v1"
            model_name = config.get("model_name") or "meta/llama-3.1-8b-instruct"
        else:
            # Fallback to Sumopod/Universal default
            api_key = os.environ.get("SUMOPOD_API_KEY") or config.get("api_key") or EMERGENT_KEY
            base_url = os.environ.get("SUMOPOD_BASE_URL") or config.get("base_url") or "https://ai.sumopod.com"
            model_name = config.get("model_name") or "gpt-4o-mini"
    else:
        # Custom provider
        api_key = config.get("api_key")
        base_url = config.get("base_url") or "https://ai.sumopod.com"
        model_name = config.get("model_name") or "gpt-4o-mini"

    # Map model names for Nvidia compatibility if using Nvidia base_url
    if base_url and "nvidia" in base_url.lower():
        if "gpt" in model_name.lower() or "claude" in model_name.lower():
            model_name = "meta/llama-3.1-8b-instruct"

    if not api_key:
        raise RuntimeError("No API key configured for LLM call.")

    import httpx
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ],
        "temperature": config.get("temperature", 0.2),
        "max_tokens": config.get("max_tokens", 4000)
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    if isinstance(data, dict) and "text" in data:
        return data["text"]
    return json.dumps(data, ensure_ascii=False)


# ============ JD EXTRACTION ============
JD_SYSTEM_PROMPT = """Anda adalah HR Analyst senior yang sangat teliti.
Tugas Anda: ekstrak kriteria terstruktur dari Teks JD / Tanggung Jawab dan Teks Spesifikasi / Kualifikasi yang diberikan.

Output Anda WAJIB berupa JSON valid dengan struktur berikut (tanpa teks lain, tanpa markdown):
{
  "target_position": "Nama jabatan yang dicari",
  "department": "Departemen jika disebut, kosong jika tidak",
  "min_experience_years": <integer, minimum tahun pengalaman, 0 jika tidak disebut>,
  "education_level": "Jenjang pendidikan minimum (SMA/SMK | D3 | D4 | S1 | S2 | S3). Ekstrak secara terpisah dari spesifikasi. Kosong jika tidak disebut.",
  "education_major": "Jurusan pendidikan yang diminta, atau 'Semua jurusan' jika tidak spesifik. Kosong jika tidak disebut.",
  "must_have": ["Daftar poin Tanggung Jawab Utama (Job Responsibilities), pecah ke masing-masing baris dan rapikan"],
  "nice_to_have": ["Daftar poin Spesifikasi, Kualifikasi, atau Persyaratan tambahan, pecah ke masing-masing baris dan rapikan (TIDAK TERMASUK jenjang pendidikan yang sudah dipisah ke education_level)"]
}
Gunakan Bahasa Indonesia untuk nilai field. Jangan hallucinate."""


async def extract_jd_criteria(jd_text: str, config: Optional[dict] = None) -> dict:
    user_msg = f"Ekstrak kriteria dari JD berikut:\n\n---\n{jd_text[:8000]}\n---\n\nKembalikan JSON saja."
    raw = await call_llm(JD_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw) or {}
    edu_level = parsed.get("education_level", "") or ""
    edu_major = parsed.get("education_major", "") or ""
    # Build education_requirement string for backward compat
    edu_req = ""
    if edu_level and edu_major:
        edu_req = f"{edu_level} - {edu_major}"
    elif edu_level:
        edu_req = edu_level
    elif edu_major:
        edu_req = edu_major
    return {
        "target_position": parsed.get("target_position", "") or "",
        "department": parsed.get("department", "") or "",
        "min_experience_years": int(parsed.get("min_experience_years", 0) or 0),
        "education_requirement": edu_req,
        "education_level": edu_level,
        "education_major": edu_major,
        "responsibilities": parsed.get("responsibilities", []) or [],
        "must_have": parsed.get("must_have", []) or [],
        "nice_to_have": parsed.get("nice_to_have", []) or [],
    }


# ============ CV PARSING ============
CV_SYSTEM_PROMPT = """Anda adalah parser CV cerdas. Ekstrak informasi terstruktur dari CV mentah.
Output WAJIB JSON valid (tanpa teks lain, tanpa markdown):
{
  "name": "Nama lengkap kandidat",
  "email": "email@example.com",
  "phone": "+62...",
  "summary": "Ringkasan profil 1-2 kalimat",
  "years_of_experience": <integer, total tahun pengalaman kerja>,
  "work_history": [
    {"position": "Jabatan", "company": "Perusahaan", "duration": "Jan 2020 - Des 2023", "achievements": ["Pencapaian 1", "Pencapaian 2"]}
  ],
  "education": [{"degree": "S1 Teknik Informatika", "institution": "Universitas X", "year": "2018"}],
  "skills": ["Skill 1", "Skill 2"],
  "certifications": ["Sertifikasi 1"],
  "languages": ["Indonesia (Native)", "English (Professional)"]
}
Jika data tidak ada, gunakan string kosong atau array kosong. Jangan hallucinate."""


async def parse_cv(cv_text: str, config: Optional[dict] = None) -> dict:
    import re
    cleaned_text = re.sub(r'[ \t]+', ' ', cv_text)
    cleaned_text = re.sub(r'\n+', '\n', cleaned_text).strip()
    user_msg = f"Parse CV berikut:\n\n---\n{cleaned_text[:8000]}\n---\n\nKembalikan JSON saja."
    raw = await call_llm(CV_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw) or {}
    return {
        "name": parsed.get("name", "") or "Unknown",
        "email": parsed.get("email", "") or "",
        "phone": parsed.get("phone", "") or "",
        "summary": parsed.get("summary", "") or "",
        "years_of_experience": int(parsed.get("years_of_experience", 0) or 0),
        "work_history": parsed.get("work_history", []) or [],
        "education": parsed.get("education", []) or [],
        "skills": parsed.get("skills", []) or [],
        "certifications": parsed.get("certifications", []) or [],
        "languages": parsed.get("languages", []) or [],
    }


# ============ SEMANTIC SCORING ============
SCORING_SYSTEM_PROMPT = """Anda adalah evaluator rekrutmen senior yang objektif dan adil.
Tugas Anda: nilai kesesuaian kandidat dengan Job Description menggunakan pemahaman SEMANTIK, bukan keyword matching.
Contoh kesetaraan: 'Salary Administration' setara 'Payroll Specialist', 'People & Culture' setara 'HR'.

PENTING — Untuk dimensi MUST-HAVE dan NICE-TO-HAVE, perhatikan kolom 'weight' pada tiap kriteria (skala 1-5).
Bobot 5 = krusial, 3 = normal, 1 = ringan. Kriteria dengan bobot lebih tinggi WAJIB lebih mempengaruhi sub-skor.

PENTING — Untuk dimensi EDUCATION, evaluasi dua sub-aspek terpisah:
1. Jenjang pendidikan (mis. S1 vs S2) — bobot ditentukan di edu_level_pct
2. Jurusan/major (mis. Akuntansi vs Teknik Industri) — bobot di edu_major_pct
Jika 'education_major' adalah 'Semua jurusan' atau kosong, anggap jurusan kandidat selalu memenuhi (skor 100 untuk komponen jurusan).
Hitung skor education = (skor_jenjang × edu_level_pct + skor_jurusan × edu_major_pct) / 100.

Output WAJIB JSON valid (tanpa teks lain, tanpa markdown):
{
  "must_have": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "experience": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "domain": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "education": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."], "level_score": <0-100>, "major_score": <0-100>},
  "nice_have": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "rationale_summary": "Ringkasan keputusan 2-3 kalimat",
  "strengths": ["Kekuatan 1", "Kekuatan 2", "Kekuatan 3"],
  "gaps_summary": ["Kekurangan 1", "Kekurangan 2"]
}
Bersikap objektif. Skor 0-39 = lemah, 40-74 = sedang, 75-100 = kuat."""


async def evaluate_match(
    jd_data: dict,
    cv_data: dict,
    config: Optional[dict] = None,
) -> dict:
    # Build weighted criteria text to make weights visible to LLM
    must_with_weights = [
        {"value": c.get("value", c) if isinstance(c, dict) else c,
         "weight": (c.get("weight", 3) if isinstance(c, dict) else 3)}
        for c in jd_data.get("must_have", [])
    ]
    nice_with_weights = [
        {"value": c.get("value", c) if isinstance(c, dict) else c,
         "weight": (c.get("weight", 3) if isinstance(c, dict) else 3)}
        for c in jd_data.get("nice_to_have", [])
    ]
    jd_summary = {
        "target_position": jd_data.get("target_position", ""),
        "department": jd_data.get("department", ""),
        "min_experience_years": jd_data.get("min_experience_years", 0),
        "education_level": jd_data.get("education_level", "") or jd_data.get("education_requirement", ""),
        "education_major": jd_data.get("education_major", "") or "Semua jurusan",
        "edu_level_pct": jd_data.get("edu_level_pct", 70),
        "edu_major_pct": jd_data.get("edu_major_pct", 30),
        "responsibilities": jd_data.get("responsibilities", []),
        "must_have": must_with_weights,
        "nice_to_have": nice_with_weights,
    }
    cv_summary = {
        "name": cv_data.get("name", ""),
        "summary": cv_data.get("summary", ""),
        "years_of_experience": cv_data.get("years_of_experience", 0),
        "work_history": cv_data.get("work_history", []),
        "education": cv_data.get("education", []),
        "skills": cv_data.get("skills", []),
        "certifications": cv_data.get("certifications", []),
    }
    user_msg = (
        "JOB DESCRIPTION:\n"
        + json.dumps(jd_summary, ensure_ascii=False, indent=2)
        + "\n\nKANDIDAT (CV):\n"
        + json.dumps(cv_summary, ensure_ascii=False, indent=2)
        + "\n\nLakukan penilaian dan kembalikan JSON saja."
    )
    raw = await call_llm(SCORING_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw) or {}

    def _dim(key: str) -> dict:
        d = parsed.get(key, {}) or {}
        out = {
            "score": max(0, min(100, int(d.get("score", 0) or 0))),
            "explanation": d.get("explanation", "") or "",
            "matched_points": d.get("matched_points", []) or [],
            "gaps": d.get("gaps", []) or [],
        }
        if key == "education":
            out["level_score"] = max(0, min(100, int(d.get("level_score", out["score"]) or 0)))
            out["major_score"] = max(0, min(100, int(d.get("major_score", out["score"]) or 0)))
        return out

    return {
        "must_have": _dim("must_have"),
        "experience": _dim("experience"),
        "domain": _dim("domain"),
        "education": _dim("education"),
        "nice_have": _dim("nice_have"),
        "rationale_summary": parsed.get("rationale_summary", "") or "",
        "strengths": parsed.get("strengths", []) or [],
        "gaps_summary": parsed.get("gaps_summary", []) or [],
    }


def calculate_total_score(dimensions: dict, weights: dict) -> int:
    """Compute weighted total score 0-100."""
    total = (
        dimensions["must_have"]["score"] * weights.get("must_have", 40) / 100
        + dimensions["experience"]["score"] * weights.get("experience", 30) / 100
        + dimensions["domain"]["score"] * weights.get("domain", 15) / 100
        + dimensions["education"]["score"] * weights.get("education", 5) / 100
        + dimensions["nice_have"]["score"] * weights.get("nice_have", 10) / 100
    )
    return max(0, min(100, round(total)))


def recommendation_from_score(score: int, weights: dict) -> str:
    shortlist = weights.get("shortlist_threshold", 75)
    reject = weights.get("reject_threshold", 40)
    if score >= shortlist:
        return "shortlist"
    if score < reject:
        return "reject"
    return "review"
