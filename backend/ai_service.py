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
    text = text.strip()
    
    # Try to find JSON block in markdown code fences anywhere in the text
    code_fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_fence_match:
        text = code_fence_match.group(1).strip()
            
    # Clean comments (single-line // and block /* */) safely (preserving URLs like https://)
    cleaned = re.sub(r'(?<!https:)(?<!http:)//.*$', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*[\s\S]*?\*/', '', cleaned).strip()
    
    try:
        return json.loads(cleaned, strict=False)
    except Exception:
        pass
        
    # Try to find first JSON object
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0), strict=False)
        except Exception:
            return None
    return None


class LLMResponse(str):
    def __new__(cls, content, usage=None):
        instance = super().__new__(cls, content)
        instance.usage = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return instance


async def call_llm(
    system_message: str,
    user_message: str,
    config: Optional[dict] = None,
    session_id: Optional[str] = None,
    response_format: Optional[dict] = None,
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
        content = resp if isinstance(resp, str) else str(resp)
        return LLMResponse(content)

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
    
    if response_format:
        payload["response_format"] = response_format
        
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response_format and e.response.status_code in (400, 422):
                logger.warning(f"LLM call failed with response_format, retrying without it: {e}")
                payload_fallback = payload.copy()
                payload_fallback.pop("response_format", None)
                resp = await client.post(url, headers=headers, json=payload_fallback)
                resp.raise_for_status()
            else:
                raise e
        data = resp.json()
        
    usage = {}
    if isinstance(data, dict):
        usage = data.get("usage", {})
        
    try:
        content = data["choices"][0]["message"]["content"]
        return LLMResponse(content, usage)
    except Exception:
        pass
    if isinstance(data, dict) and "text" in data:
        return LLMResponse(data["text"], usage)
    return LLMResponse(json.dumps(data, ensure_ascii=False), usage)


# ============ JD EXTRACTION ============
JD_SYSTEM_PROMPT = """Anda adalah HR Analyst senior yang sangat teliti.
Tugas Anda: ekstrak kriteria terstruktur dari teks Job Description (JD) yang diberikan.

Output Anda WAJIB berupa JSON valid dengan struktur berikut (tanpa teks lain, tanpa markdown):
{
  "target_position": "Nama jabatan yang dicari",
  "department": "Departemen jika disebut, kosong jika tidak",
  "min_experience_years": <integer, minimum tahun pengalaman, 0 jika tidak disebut>,
  "education_level": "Jenjang pendidikan minimum (SMA/SMK | D3 | D4 | S1 | S2 | S3). Ekstrak secara terpisah dari spesifikasi. Kosong jika tidak disebut.",
  "education_major": "Jurusan pendidikan yang diminta, atau 'Semua jurusan' jika tidak spesifik. Kosong jika tidak disebut.",
  "responsibilities": ["Daftar poin Tanggung Jawab Utama / Job Duties, pecah ke masing-masing baris dan rapikan"],
  "must_have": ["Daftar KOMPETENSI, KEAHLIAN, atau SKILL yang WAJIB dimiliki kandidat (bukan tugas/deskripsi pekerjaan). Contoh: 'Ahli K3 Umum', 'Menguasai Python', 'Sertifikat ISO 45001'. Pecah per item."],
  "nice_to_have": ["Daftar kualifikasi tambahan / preferred (TIDAK TERMASUK jenjang pendidikan yang sudah dipisah ke education_level). Pecah per item."]
}
PENTING: 
- "must_have" harus berisi SKILL/KOMPETENSI/SERTIFIKASI yang bisa dicocokkan dengan profil kandidat, BUKAN deskripsi tugas.
- "responsibilities" berisi deskripsi tugas/tanggung jawab pekerjaan yang akan dijalankan.
- Jika JD tidak memisahkan keduanya secara eksplisit, inferensikan: kalimat kerja aktif (mengawasi, membuat laporan, dll) → responsibilities. Kompetensi/keahlian/sertifikasi → must_have.
Gunakan Bahasa Indonesia untuk nilai field. Jangan hallucinate."""


async def extract_jd_criteria(jd_text: str, config: Optional[dict] = None) -> dict:
    user_msg = f"Ekstrak kriteria dari JD berikut:\n\n---\n{jd_text[:8000]}\n---\n\nKembalikan JSON saja."
    raw = await call_llm(JD_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw)
    if parsed is None:
        raise ValueError(f"Gagal mengekstrak kriteria dari respons AI. Respons mentah: {str(raw)[:500]}")
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
CV_SYSTEM_PROMPT = """Anda adalah parser CV cerdas. Ekstrak informasi terstruktur secara akurat dari CV mentah.
Output WAJIB berupa JSON valid (tanpa penjelasan tambahan, tanpa markdown):
{
  "name": "Nama lengkap kandidat",
  "email": "Alamat email kandidat",
  "phone": "Nomor telepon/WhatsApp kandidat",
  "gender": "laki-laki | perempuan (Tentukan secara akurat berdasarkan nama lengkap, sapaan Bp/Ibu, foto/deskripsi diri, atau informasi gender eksplisit di CV. Contoh: Syaiful / Nasrullah = laki-laki)",
  "birth_date": "Tanggal lahir kandidat format YYYY-MM-DD (Ekstrak dari tempat/tanggal lahir kandidat, misal lahir 12 April 1990 -> 1990-04-12. Jika hanya ada tahun lahir atau umur, perkirakan tanggalnya)",
  "address": "Alamat lengkap tempat tinggal kandidat, kosong jika tidak ditemukan",
  "summary": "Ringkasan profil 1-2 kalimat",
  "years_of_experience": <integer, total tahun pengalaman kerja. PENTING: Hitung secara akurat berdasarkan selisih tahun dari pekerjaan PERTAMA kali dimulai hingga pekerjaan TERAKHIR atau hari ini (jika berstatus 'Sekarang' / 'Present'). KETENTUAN HARI INI: Gunakan TAHUN 2026 sebagai tahun sekarang. Contoh: jika bekerja pertama kali Juli 2009 sampai Sekarang (2026), maka lama pengalamannya adalah 2026 - 2009 = 17 tahun!>,
  "skills": [
    {
      "skill_name": "Nama keahlian/skill (misal: React, Python, Excel)",
      "years_of_experience": <float/number, estimasi tahun pengalaman untuk keahlian ini>,
      "proficiency_level": "junior | mid | senior (Tingkat kemahiran berdasarkan informasi di CV atau durasi pengalaman)"
    }
  ],
  "education": [
    {
      "degree": "Jenjang pendidikan (misal: S1, S2, D3, SMA/SMK)",
      "major": "Jurusan pendidikan (misal: Teknik Informatika, Akuntansi)",
      "institution": "Nama institusi/universitas/sekolah",
      "year": "Tahun kelulusan (jika ada, misal: 2017)"
    }
  ],
  "experience": [
    {
      "role": "Jabatan/Pekerjaan (misal: Frontend Developer, Payroll Specialist)",
      "company": "Nama perusahaan",
      "duration_months": <integer, total durasi bekerja dalam satuan bulan di posisi ini. Hitung secara akurat berdasarkan rentang bulan/tahun mulai hingga selesai. Contoh: Jan 2020 - Des 2020 = 12 bulan>,
      "responsibilities": ["Daftar tanggung jawab, tugas, pencapaian, atau bullet points/detail pekerjaan dari posisi ini"]
    }
  ],
  "projects": [
    {
      "project_name": "Nama proyek yang pernah dikerjakan (kosongkan jika tidak ada)",
      "tech_stack": ["Daftar teknologi/bahasa/framework yang digunakan di proyek ini"]
    }
  ],
  "certifications": ["Daftar sertifikat kompetensi resmi, lisensi profesi, atau pelatihan formal berlisensi (misal: Ahli K3 Umum, BNSP)"],
  "achievements": ["Daftar prestasi atau penghargaan formal yang diperoleh kandidat"],
  "languages": ["Daftar bahasa yang dikuasai beserta tingkat kemampuannya"]
}
PENTING TERKAIT LAYOUT & MULTI-KOLOM:
Jika karena konversi PDF multi-kolom, ada judul pekerjaan baru (posisi baru) yang tergabung di akhir baris bullet point pekerjaan sebelumnya, Anda WAJIB memisahkannya secara bersih menjadi objek pengalaman kerja (experience) tersendiri di dalam array. Jangan biarkan tergabung sebagai satu bullet point.

PENTING: Jangan sekali-kali memasukkan teks panduan/contoh di atas ke dalam output jika kandidat tidak memilikinya di CV. Jika suatu data tidak ditemukan di CV, gunakan string kosong "" atau array kosong []. Jangan berhalusinasi."""


async def parse_cv(cv_text: str, config: Optional[dict] = None) -> dict:
    import re
    cleaned_text = re.sub(r'[ \t]+', ' ', cv_text)
    cleaned_text = re.sub(r'\n+', '\n', cleaned_text).strip()
    user_msg = f"Parse CV berikut:\n\n---\n{cleaned_text[:60000]}\n---\n\nKembalikan JSON saja."
    raw = await call_llm(CV_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw)
    if parsed is None:
        raise ValueError(f"Gagal mengekstrak data CV dari respons AI. Respons mentah: {str(raw)[:500]}")
    usage = getattr(raw, "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    
    # Extract new structured arrays
    skills = parsed.get("skills", []) or []
    education = parsed.get("education", []) or []
    experience = parsed.get("experience", []) or []
    projects = parsed.get("projects", []) or []
    
    # Build legacy work_history list for UI backward compatibility
    work_history = []
    for exp in experience:
        if isinstance(exp, dict):
            dur_m = exp.get("duration_months", 0)
            duration_str = f"{dur_m} bulan" if dur_m else ""
            work_history.append({
                "position": exp.get("role", "") or "",
                "company": exp.get("company", "") or "",
                "duration": duration_str,
                "achievements": exp.get("responsibilities", []) or []
            })
            
    # Deduplicate list helper
    def dedup_list(lst):
        seen = set()
        out = []
        for item in lst:
            if isinstance(item, dict):
                name = item.get("skill_name", "")
                if name:
                    key = name.strip().lower()
                    if key not in seen:
                        seen.add(key)
                        out.append(item)
            elif isinstance(item, str):
                key = item.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    out.append(item.strip())
            else:
                out.append(item)
        return out

    # Deduplicate skills list first
    skills = dedup_list(skills)

    # Derive legacy hard_skills / soft_skills from skills array if not explicitly returned
    hard_skills = []
    soft_skills = []
    soft_keywords = [
        "hr", "recruitment", "human resources", "communication", "leadership", "budgeting", 
        "management", "teamwork", "negotiation", "problem solving", "time management", 
        "critical thinking", "adaptability", "conflict resolution", "interpersonal", 
        "public speaking", "asset", "administration", "pengelolaan", "komunikasi", "kepemimpinan",
        "public relation", "presentasi", "adaptif", "analitis", "kreatif", "negosiasi"
    ]
    for s in skills:
        if isinstance(s, dict):
            name = s.get("skill_name", "")
            if name:
                lower = name.lower()
                if any(kw in lower for kw in soft_keywords):
                    soft_skills.append(name)
                else:
                    hard_skills.append(name)
        elif isinstance(s, str):
            lower = s.lower()
            if any(kw in lower for kw in soft_keywords):
                soft_skills.append(s)
            else:
                hard_skills.append(s)

    # Deduplicate other extracted lists
    certifications = dedup_list(parsed.get("certifications", []) or [])
    achievements = dedup_list(parsed.get("achievements", []) or [])
    languages = dedup_list(parsed.get("languages", []) or [])

    return {
        "name": parsed.get("name", "") or "Unknown",
        "email": parsed.get("email", "") or "",
        "phone": parsed.get("phone", "") or "",
        "summary": parsed.get("summary", "") or "",
        "years_of_experience": int(parsed.get("years_of_experience", 0) or 0),
        "gender": parsed.get("gender", "") or "",
        "birth_date": parsed.get("birth_date", "") or "",
        "address": parsed.get("address", "") or "",
        "work_history": work_history,
        "education": education,
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "certifications": certifications,
        "achievements": achievements,
        "languages": languages,
        "_usage": usage,
    }


# ============ SEMANTIC MATCHING HELPERS ============
SYNONYM_MAP = {
    "react": ["reactjs", "react.js", "frontend", "web developer", "react developer"],
    "reactjs": ["react", "react.js", "frontend", "web developer", "react developer"],
    "frontend": ["web developer", "frontend developer", "react", "reactjs", "vue", "angular"],
    "web developer": ["frontend", "frontend developer", "backend developer", "fullstack developer", "web dev"],
    "js": ["javascript", "es6"],
    "javascript": ["js", "es6"],
    "ts": ["typescript"],
    "typescript": ["ts"],
    "python": ["py", "python3"],
    "golang": ["go"],
    "postgres": ["postgresql", "postgres sql"],
    "mongodb": ["mongo"],
    "vue": ["vuejs", "vue.js"],
    "aws": ["amazon web services", "cloud"],
    "hse": ["k3", "ahli k3", "safety officer", "health safety environment", "hse officer", "hse supervisor", "hse lead", "k3 umum", "safety supervisor"],
    "k3": ["hse", "ahli k3", "safety officer", "health safety environment", "hse officer", "hse supervisor", "hse lead", "k3 umum", "safety supervisor"],
    "ahli k3": ["hse", "k3", "safety officer", "health safety environment", "hse officer", "hse supervisor", "hse lead", "k3 umum", "safety supervisor"],
    "safety officer": ["hse", "k3", "ahli k3", "health safety environment", "hse officer", "hse supervisor", "hse lead", "k3 umum", "safety supervisor"],
    "payroll": ["gaji", "penggajian", "payroll specialist", "salary administration", "payroll administration"],
    "excel": ["ms excel", "microsoft excel", "spreadsheet", "spreadsheets"],
    "hr": ["human resources", "hrd", "people culture", "people operations", "personalia", "sumber daya manusia"],
    "human resources": ["hr", "hrd", "people culture", "people operations", "personalia", "sumber daya manusia"],
    "hrd": ["hr", "human resources", "people culture", "people operations", "personalia", "sumber daya manusia"],
}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text

def are_synonyms(a: str, b: str) -> bool:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    
    # Direct synonym lookup
    for syn_key, syn_list in SYNONYM_MAP.items():
        if a_norm == syn_key and b_norm in syn_list:
            return True
        if b_norm == syn_key and a_norm in syn_list:
            return True
            
    # Substring match
    if a_norm in b_norm or b_norm in a_norm:
        return True
        
    return False

def get_edu_level(degree: str) -> int:
    if not degree:
        return 0
    d = degree.upper()
    if "S3" in d or "DOKTOR" in d or "PHD" in d or "PH.D" in d:
        return 6
    if "S2" in d or "MAGISTER" in d or "MASTER" in d or "MBA" in d:
        return 5
    if "S1" in d or "SARJANA" in d or "BACHELOR" in d:
        return 4
    if "D4" in d or "DIPLOMA 4" in d:
        return 3
    if "D3" in d or "DIPLOMA 3" in d:
        return 2
    if "SMA" in d or "SMK" in d or "HIGH SCHOOL" in d:
        return 1
    return 0

def match_criterion(criterion_val: str, cv_data: dict) -> bool:
    c_norm = normalize_text(criterion_val)
    if not c_norm:
        return False

    def _text_contains(text: str) -> bool:
        """Check if criterion is contained in / synonymous with a text blob."""
        if not text:
            return False
        t_norm = normalize_text(text)
        if are_synonyms(c_norm, t_norm):
            return True
        # keyword-in-text check: all words of criterion found in text
        c_words = [w for w in c_norm.split() if len(w) > 2]
        if c_words and all(w in t_norm for w in c_words):
            return True
        return False

    # Check in skills
    for s in cv_data.get("skills", []):
        s_name = s.get("skill_name", "") if isinstance(s, dict) else str(s)
        if are_synonyms(c_norm, s_name):
            return True

    # Check in hard_skills / soft_skills (legacy string lists)
    for s in cv_data.get("hard_skills", []) + cv_data.get("soft_skills", []):
        if are_synonyms(c_norm, s):
            return True

    # Check in certifications
    for cert in cv_data.get("certifications", []):
        if are_synonyms(c_norm, cert):
            return True

    # Check in languages
    for lang in cv_data.get("languages", []):
        if are_synonyms(c_norm, lang):
            return True

    # Check in projects
    for p in cv_data.get("projects", []):
        p_name = p.get("project_name", "") if isinstance(p, dict) else ""
        if are_synonyms(c_norm, p_name):
            return True
        for ts in p.get("tech_stack", []):
            if are_synonyms(c_norm, ts):
                return True

    # Check in experience — role, company, AND responsibilities descriptions
    for exp in cv_data.get("experience", []):
        role = exp.get("role", "") if isinstance(exp, dict) else ""
        comp = exp.get("company", "") if isinstance(exp, dict) else ""
        if are_synonyms(c_norm, role) or are_synonyms(c_norm, comp):
            return True
        for resp in exp.get("responsibilities", []):
            if _text_contains(resp):
                return True

    # Check in summary
    if _text_contains(cv_data.get("summary", "")):
        return True

    return False


SCORING_SYSTEM_PROMPT = """Anda adalah seorang AI Recruitment Expert dan Senior HR Analyst profesional.
Tugas Anda adalah melakukan evaluasi mendalam terhadap CV kandidat berdasarkan kualifikasi lowongan (Job Requirement) dan data ekstraksi ATS, kemudian merumuskan KEKUATAN (strengths), KEKURANGAN (gaps_summary), dan KESIMPULAN (rationale_summary) secara akurat, logis, dan bebas dari kontradiksi teks.

### ANALYSIS GUIDELINES (WAJIB DIIKUTI):
1. **Validasi Terminologi:** Sadari bahwa HSE (Health, Safety, Environment), EHS, K3 (Keselamatan dan Kesehatan Kerja), dan "Health, Safety, and Security" berada dalam rumpun ilmu dan fungsi yang beririsan sangat dekat. Jangan menyatakan kandidat "tidak memiliki pengalaman di bidang Safety/Security" jika CV-nya jelas-jelas menunjukkan sertifikasi Ahli K3 Umum/Muda, ISO 45001, atau pengelolaan insiden keselamatan kerja.
2. **Konsistensi Logis:** JANGAN PERNAH mengeluarkan kalimat kontradiktif dalam satu paragraf (Contoh salah: "Kandidat memiliki pengalaman sangat relevan di bidang HSE, namun tidak memiliki pengalaman di bidang keselamatan"). Jika ada gap, sebutkan secara spesifik pada aspek apa (misal: "Kandidat kuat di HSE manufaktur/klinis, namun minim di handle Security fisik atau loss prevention").
3. **Kekuatan (strengths):** Fokus pada pencapaian terukur (metrics/achievements), sertifikasi profesi resmi yang valid (seperti BNSP, Kemnaker, ISO), serta durasi dan kedalaman pengalaman di industri terkait.
   Format pengisian list "strengths" (gunakan format teks tebal markdown untuk aspek kompetensi):
   "**[Aspek Kompetensi]**: [Penjelasan berbasis bukti dari CV, sertakan angka/sertifikasi jika ada]"
4. **Kekurangan (gaps_summary):** Fokus pada gap nyata antara CV kandidat dengan Job Requirement (misal: kurangnya sertifikasi spesifik, belum memiliki pengalaman di industri tertentu, atau durasi kerja yang terlalu singkat/kutu loncat jika ada). Jangan membuat kelemahan generik yang membantah fakta di bagian Kekuatan.
   Format pengisian list "gaps_summary" (gunakan format teks tebal markdown untuk aspek gap):
   "**[Aspek Gap]**: [Penjelasan gap nyata terhadap requirement, misal: belum memiliki sertifikasi X atau pengalaman di bidang Y]"
5. **Kesimpulan (rationale_summary):** Tulis 1 paragraf evaluasi akhir (maksimal 4 kalimat). Evaluasi harus memberikan gambaran utuh: seberapa cocok kandidat dengan posisi yang dilamar, di mana letak keunggulan utamanya, dan apa risiko/kekurangan terbesar kandidat yang perlu dikonfirmasi saat interview. Jaga agar kalimat tetap logis, selaras dengan skor kuantitatif yang dihitung, dan tidak saling bertabrakan.

### OUTPUT FORMAT:
Kembalikan respon hanya berupa objek JSON valid tanpa markdown fence (```json) dan tanpa penjelasan preamble apa pun. Struktur JSON harus persis seperti berikut:
{
  "must_have": {
    "explanation": "penjelasan...",
    "matched_points": ["..."],
    "gaps": ["..."]
  },
  "experience": {
    "explanation": "penjelasan...",
    "matched_points": ["..."],
    "gaps": ["..."]
  },
  "domain": {
    "explanation": "penjelasan...",
    "matched_points": ["..."],
    "gaps": ["..."]
  },
  "education": {
    "explanation": "penjelasan...",
    "matched_points": ["..."],
    "gaps": ["..."]
  },
  "nice_have": {
    "explanation": "penjelasan...",
    "matched_points": ["..."],
    "gaps": ["..."]
  },
  "rationale_summary": "Teks paragraf kesimpulan evaluasi akhir (max 4 kalimat)",
  "strengths": [
    "**Aspek Kompetensi**: Penjelasan berbasis bukti...",
    "**Aspek Kompetensi**: Penjelasan berbasis bukti..."
  ],
  "gaps_summary": [
    "**Aspek Gap**: Penjelasan gap nyata...",
    "**Aspek Gap**: Penjelasan gap nyata..."
  ]
}
"""


async def evaluate_match(
    jd_data: dict,
    cv_data: dict,
    config: Optional[dict] = None,
) -> dict:
    weights = jd_data.get("weights", {}) or {}
    
    # 1. Must-have score calculation
    must_have_criteria = jd_data.get("must_have", [])
    if not must_have_criteria:
        must_have_score = 100
        must_matched = []
        must_gaps = []
    else:
        total_must_weight = 0
        matched_must_weight = 0
        must_matched = []
        must_gaps = []
        for c in must_have_criteria:
            val = c.get("value", "")
            wt = c.get("weight", 3)
            total_must_weight += wt
            if match_criterion(val, cv_data):
                matched_must_weight += wt
                must_matched.append(val)
            else:
                must_gaps.append(val)
        must_have_score = round((matched_must_weight / total_must_weight) * 100) if total_must_weight > 0 else 100

    # 2. Nice-to-have score calculation
    nice_have_criteria = jd_data.get("nice_to_have", [])
    if not nice_have_criteria:
        nice_have_score = 100
        nice_matched = []
        nice_gaps = []
    else:
        total_nice_weight = 0
        matched_nice_weight = 0
        nice_matched = []
        nice_gaps = []
        for c in nice_have_criteria:
            val = c.get("value", "")
            wt = c.get("weight", 3)
            total_nice_weight += wt
            if match_criterion(val, cv_data):
                matched_nice_weight += wt
                nice_matched.append(val)
            else:
                nice_gaps.append(val)
        nice_have_score = round((matched_nice_weight / total_nice_weight) * 100) if total_nice_weight > 0 else 100

    # 3. Experience score calculation
    min_exp_years = jd_data.get("min_experience_years", 0)
    target_pos = jd_data.get("target_position", "")
    target_norm = normalize_text(target_pos)
    
    total_months = 0
    relevant_months = 0
    for exp in cv_data.get("experience", []):
        r_months = exp.get("duration_months", 0)
        total_months += r_months
        role = exp.get("role", "")
        if not target_norm or are_synonyms(target_pos, role) or target_norm in normalize_text(role) or normalize_text(role) in target_norm:
            relevant_months += r_months
        else:
            matched_any = False
            for m_c in must_have_criteria:
                val = m_c.get("value", "")
                if normalize_text(val) in normalize_text(role):
                    matched_any = True
                    break
            if matched_any:
                relevant_months += r_months

    actual_months = relevant_months if relevant_months > 0 else total_months
    if actual_months == 0:
        # Fallback ke years_of_experience yang dihitung LLM dari teks CV
        actual_months = cv_data.get("years_of_experience", 0) * 12
    actual_years = actual_months / 12.0
    if min_exp_years <= 0:
        experience_score = 100
    else:
        experience_score = min(100, round((actual_years / min_exp_years) * 100))

    # 4. Education score calculation
    req_level_str = jd_data.get("education_level", "")
    req_major_str = jd_data.get("education_major", "")
    edu_level_pct = jd_data.get("edu_level_pct", 70)
    edu_major_pct = jd_data.get("edu_major_pct", 30)
    
    req_level = get_edu_level(req_level_str)
    
    best_level_score = 0
    best_major_score = 0
    best_edu_score = 0
    
    candidate_edus = cv_data.get("education", [])
    if not candidate_edus:
        if req_level <= 1:
            best_level_score = 100
            best_major_score = 100
            best_edu_score = 100
        else:
            best_level_score = 0
            best_major_score = 0
            best_edu_score = 0
    else:
        for edu in candidate_edus:
            degree = edu.get("degree", "")
            major = edu.get("major", "")
            
            cand_level = get_edu_level(degree)
            if req_level <= 0:
                lvl_score = 100
            elif cand_level >= req_level:
                lvl_score = 100
            else:
                lvl_score = max(0, 100 - (req_level - cand_level) * 30)
                
            if not req_major_str or req_major_str.lower() in ("semua jurusan", ""):
                maj_score = 100
            else:
                if are_synonyms(req_major_str, major) or normalize_text(req_major_str) in normalize_text(major) or normalize_text(major) in normalize_text(req_major_str):
                    maj_score = 100
                else:
                    maj_score = 0
                    req_norm = normalize_text(req_major_str)
                    maj_norm = normalize_text(major)
                    
                    major_syns = [
                        ["informatika", "computer", "komputer", "sistem informasi", "software", "it", "teknologi informasi"],
                        ["ekonomi", "akuntansi", "manajemen", "bisnis", "finance", "keuangan"],
                        ["hukum", "law"],
                        ["psikologi", "psychology"],
                        ["industri", "industrial"],
                        ["komunikasi", "hubungan masyarakat", "humas", "public relations"],
                    ]
                    for group in major_syns:
                        if any(g in req_norm for g in group) and any(g in maj_norm for g in group):
                            maj_score = 80
                            break
                            
            edu_score = round((lvl_score * edu_level_pct + maj_score * edu_major_pct) / 100)
            if edu_score > best_edu_score:
                best_edu_score = edu_score
                best_level_score = lvl_score
                best_major_score = maj_score

    # 5. Domain score calculation
    domain_score = 0
    if not target_pos:
        domain_score = 100
    else:
        for exp in cv_data.get("experience", []):
            role = exp.get("role", "")
            if are_synonyms(target_pos, role) or target_norm in normalize_text(role) or normalize_text(role) in target_norm:
                domain_score = 100
                break
        if domain_score == 0:
            for s in cv_data.get("skills", []):
                s_name = s.get("skill_name", "") if isinstance(s, dict) else str(s)
                if are_synonyms(target_pos, s_name):
                    domain_score = 80
                    break
        if domain_score == 0:
            for exp in cv_data.get("experience", []):
                role = exp.get("role", "")
                words_target = set(target_norm.split())
                words_role = set(normalize_text(role).split())
                if words_target.intersection(words_role):
                    domain_score = 60
                    break
        if domain_score == 0:
            domain_score = 30

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
        "experience": cv_data.get("experience", []),
        "education": cv_data.get("education", []),
        "skills": cv_data.get("skills", []),
        "certifications": cv_data.get("certifications", []),
    }
    
    user_msg = (
        "JOB DESCRIPTION:\n"
        + json.dumps(jd_summary, ensure_ascii=False, indent=2)
        + "\n\nKANDIDAT (CV):\n"
        + json.dumps(cv_summary, ensure_ascii=False, indent=2)
        + f"\n\nSistem telah menghitung skor kuantitatif berikut:\n"
        f"- must_have: {must_have_score}\n"
        f"- experience: {experience_score}\n"
        f"- domain: {domain_score}\n"
        f"- education: {best_edu_score} (level_score: {best_level_score}, major_score: {best_major_score})\n"
        f"- nice_have: {nice_have_score}\n\n"
        f"Bobot dimensi global (dari JobPosting):\n"
        f"- must_have: {weights.get('must_have', 40)}%\n"
        f"- experience: {weights.get('experience', 30)}%\n"
        f"- domain: {weights.get('domain', 15)}%\n"
        f"- education: {weights.get('education', 5)}%\n"
        f"- nice_have: {weights.get('nice_have', 10)}%\n\n"
        "TUGAS ANDA:\n"
        "Tulis penjelasan kualitatif (explanation, rationale_summary, strengths, gaps) yang sepenuhnya selaras dengan skor kuantitatif di atas untuk mencegah kontradiksi.\n"
        "Kembalikan JSON saja dengan struktur:\n"
        "{\n"
        f'  "must_have": {{"score": {must_have_score}, "explanation": "penjelasan...", "matched_points": ["..."], "gaps": ["..."]}},\n'
        f'  "experience": {{"score": {experience_score}, "explanation": "penjelasan...", "matched_points": ["..."], "gaps": ["..."]}},\n'
        f'  "domain": {{"score": {domain_score}, "explanation": "penjelasan...", "matched_points": ["..."], "gaps": ["..."]}},\n'
        f'  "education": {{"score": {best_edu_score}, "explanation": "penjelasan...", "matched_points": ["..."], "gaps": ["..."], "level_score": {best_level_score}, "major_score": {best_major_score}}},\n'
        f'  "nice_have": {{"score": {nice_have_score}, "explanation": "penjelasan...", "matched_points": ["..."], "gaps": ["..."]}},\n'
        '  "rationale_summary": "Ringkasan keputusan...",\n'
        '  "strengths": ["..."],\n'
        '  "gaps_summary": ["..."]\n'
        "}"
    )
    
    raw = await call_llm(SCORING_SYSTEM_PROMPT, user_msg, config)
    parsed = _extract_json(raw)
    if parsed is None:
        raise ValueError(f"Gagal mengekstrak hasil penilaian dari respons AI. Respons mentah: {str(raw)[:500]}")
    usage = getattr(raw, "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

    def _dim(key: str, calculated_score: int) -> dict:
        d = parsed.get(key, {}) or {}
        out = {
            "score": calculated_score,
            "explanation": d.get("explanation", "") or "",
            "matched_points": d.get("matched_points", []) or [],
            "gaps": d.get("gaps", []) or [],
        }
        if key == "education":
            out["level_score"] = best_level_score
            out["major_score"] = best_major_score
        return out


    return {
        "must_have": _dim("must_have", must_have_score),
        "experience": _dim("experience", experience_score),
        "domain": _dim("domain", domain_score),
        "education": _dim("education", best_edu_score),
        "nice_have": _dim("nice_have", nice_have_score),
        "rationale_summary": parsed.get("rationale_summary", "") or "",
        "strengths": parsed.get("strengths", []) or [],
        "gaps_summary": parsed.get("gaps_summary", []) or [],
        "_usage": usage,
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


async def generate_embedding(text: str, config: Optional[dict] = None) -> list[float]:
    """Generate vector embedding for a given text using the configured AI provider."""
    config = config or {}
    api_key = config.get("api_key") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("SUMOPOD_API_KEY") or EMERGENT_KEY
    base_url = config.get("base_url") or os.environ.get("SUMOPOD_BASE_URL") or "https://ai.sumopod.com"
    provider_type = config.get("provider_type", "emergent")

    import httpx
    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Model selection
    model_name = "text-embedding-3-small"
    if "nvidia" in base_url.lower():
        model_name = "nvidia/embeddings-nv-embed-qa-4"

    payload = {
        "model": model_name,
        "input": text[:8000] # truncate to stay within token limits
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"Failed to generate embedding with config {base_url}: {e}. Attempting fallback to sumopod config...")
        try:
            from server import async_session
            from models import DBAIProviderConfig
            from sqlalchemy import select
            async with async_session() as db_session:
                stmt = select(DBAIProviderConfig).where(DBAIProviderConfig.name == "sumopod")
                res = await db_session.execute(stmt)
                sumopod_cfg = res.scalar_one_or_none()
                if sumopod_cfg and sumopod_cfg.api_key:
                    fallback_url = f"{sumopod_cfg.base_url.rstrip('/')}/embeddings"
                    fallback_headers = {
                        "Authorization": f"Bearer {sumopod_cfg.api_key}",
                        "Content-Type": "application/json"
                    }
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(fallback_url, headers=fallback_headers, json=payload)
                        resp.raise_for_status()
                        data = resp.json()
                        logger.info("Successfully generated embedding using sumopod fallback config.")
                        return data["data"][0]["embedding"]
        except Exception as fallback_err:
            logger.error(f"Fallback to sumopod also failed: {fallback_err}")
            
        logger.error(f"Error generating embedding: {e}")
        # Return a zero vector of size 1536 as fallback if API call fails
        return [0.0] * 1536
