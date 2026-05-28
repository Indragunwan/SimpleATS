"""AI Service: JD extraction, CV parsing, semantic matching, rationale generation."""
import json
import logging
import os
import re
import uuid
from typing import Any, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

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
    """Call LLM. Uses Emergent Universal Key by default; supports custom OpenAI-compatible providers."""
    config = config or {}
    provider_type = config.get("provider_type", "emergent")

    if provider_type == "emergent":
        api_key = EMERGENT_KEY
        llm_provider = config.get("llm_provider", "anthropic")
        model_name = config.get("model_name", "claude-sonnet-4-6")
    else:
        # custom OpenAI-compatible provider via LlmChat
        api_key = config.get("api_key") or EMERGENT_KEY
        llm_provider = config.get("llm_provider", "openai")
        model_name = config.get("model_name", "gpt-4o-mini")

    sid = session_id or f"cvscreen-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(
        api_key=api_key,
        session_id=sid,
        system_message=system_message,
    ).with_model(llm_provider, model_name)

    response = await chat.send_message(UserMessage(text=user_message))
    return response if isinstance(response, str) else str(response)


# ============ JD EXTRACTION ============
JD_SYSTEM_PROMPT = """Anda adalah HR Analyst senior yang sangat teliti.
Tugas Anda: ekstrak kriteria terstruktur dari teks Job Description (JD) yang diberikan.

Output Anda WAJIB berupa JSON valid dengan struktur berikut (tanpa teks lain, tanpa markdown):
{
  "target_position": "Nama jabatan yang dicari",
  "department": "Departemen jika disebut, kosong jika tidak",
  "min_experience_years": <integer, minimum tahun pengalaman, 0 jika tidak disebut>,
  "education_requirement": "Latar belakang pendidikan minimum yang diminta",
  "responsibilities": ["Tanggung jawab 1", "Tanggung jawab 2", ...],
  "must_have": ["Keahlian/kualifikasi wajib 1", "Keahlian wajib 2", ...],
  "nice_to_have": ["Keahlian tambahan 1", "Keahlian tambahan 2", ...]
}
Gunakan Bahasa Indonesia untuk nilai field. Jangan hallucinate."""


async def extract_jd_criteria(jd_text: str, config: Optional[dict] = None) -> dict:
    user_msg = f"Ekstrak kriteria dari JD berikut:\n\n---\n{jd_text[:8000]}\n---\n\nKembalikan JSON saja."
    raw = await call_llm(JD_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw) or {}
    return {
        "target_position": parsed.get("target_position", "") or "",
        "department": parsed.get("department", "") or "",
        "min_experience_years": int(parsed.get("min_experience_years", 0) or 0),
        "education_requirement": parsed.get("education_requirement", "") or "",
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
    user_msg = f"Parse CV berikut:\n\n---\n{cv_text[:10000]}\n---\n\nKembalikan JSON saja."
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

Berikan penilaian per dimensi (skala 0-100) dengan penjelasan singkat dalam Bahasa Indonesia.

Output WAJIB JSON valid (tanpa teks lain, tanpa markdown):
{
  "must_have": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "experience": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "domain": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
  "education": {"score": <0-100>, "explanation": "...", "matched_points": ["..."], "gaps": ["..."]},
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
    jd_summary = {
        "target_position": jd_data.get("target_position", ""),
        "department": jd_data.get("department", ""),
        "min_experience_years": jd_data.get("min_experience_years", 0),
        "education_requirement": jd_data.get("education_requirement", ""),
        "responsibilities": jd_data.get("responsibilities", []),
        "must_have": jd_data.get("must_have", []),
        "nice_to_have": jd_data.get("nice_to_have", []),
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
        return {
            "score": max(0, min(100, int(d.get("score", 0) or 0))),
            "explanation": d.get("explanation", "") or "",
            "matched_points": d.get("matched_points", []) or [],
            "gaps": d.get("gaps", []) or [],
        }

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
