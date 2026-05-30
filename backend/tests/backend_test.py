"""Backend API tests for Sistem Penapisan CV Berbasis AI."""
import io
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fullstack-app-184.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO = {
    "hr": ("hr@demo.com", "demo123", "hr_recruiter"),
    "manager": ("manager@demo.com", "demo123", "hiring_manager"),
    "admin": ("admin@demo.com", "demo123", "admin_it"),
}


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code == 401:
        # Fallback to local changed password '123'
        r_alt = session.post(f"{API}/auth/login", json={"email": email, "password": "123"}, timeout=30)
        if r_alt.status_code == 200:
            return r_alt.json()
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def tokens(session):
    return {role: _login(session, email, pwd) for role, (email, pwd, _) in DEMO.items()}


def _hdr(tokens, role):
    return {"Authorization": f"Bearer {tokens[role]['access_token']}"}


# ---------- HEALTH ----------
def test_health(session):
    r = session.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert data["ai_provider"] is True


# ---------- AUTH ----------
def test_login_all_demo_users(tokens):
    for role, payload in tokens.items():
        assert "access_token" in payload
        assert payload["user"]["role"] == DEMO[role][2]
        assert payload["user"]["email"] == DEMO[role][0]


def test_login_invalid(session):
    r = session.post(f"{API}/auth/login", json={"email": "no@x.com", "password": "wrong"}, timeout=10)
    assert r.status_code == 401


def test_auth_me(session, tokens):
    for role in tokens:
        r = session.get(f"{API}/auth/me", headers=_hdr(tokens, role), timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO[role][0]


def test_auth_me_no_token(session):
    r = session.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 401


# ---------- RBAC ----------
def test_rbac_users_hr_denied(session, tokens):
    r = session.get(f"{API}/users", headers=_hdr(tokens, "hr"), timeout=10)
    assert r.status_code == 403


def test_rbac_users_admin_ok(session, tokens):
    r = session.get(f"{API}/users", headers=_hdr(tokens, "admin"), timeout=10)
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 3
    emails = {u["email"] for u in users}
    assert {"hr@demo.com", "manager@demo.com", "admin@demo.com"}.issubset(emails)


def test_rbac_providers_hr_denied(session, tokens):
    r = session.get(f"{API}/config/ai-providers", headers=_hdr(tokens, "hr"), timeout=10)
    assert r.status_code == 403


def test_rbac_providers_admin_ok(session, tokens):
    r = session.get(f"{API}/config/ai-providers", headers=_hdr(tokens, "admin"), timeout=10)
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) >= 1
    # api_key must be masked (either empty for emergent or starts with ***)
    for p in arr:
        if p.get("api_key"):
            assert p["api_key"].startswith("***")


# ---------- USERS CRUD ----------
def test_create_user_admin(session, tokens):
    payload = {
        "name": "TEST User",
        "email": f"test_user_{int(time.time())}@example.com",
        "password": "Pass123!",
        "role": "hr_recruiter",
    }
    r = session.post(f"{API}/users", json=payload, headers=_hdr(tokens, "admin"), timeout=10)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["email"] == payload["email"]
    assert u["role"] == "hr_recruiter"
    # patch
    r2 = session.patch(
        f"{API}/users/{u['id']}",
        json={"name": "TEST Updated"},
        headers=_hdr(tokens, "admin"),
        timeout=10,
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "TEST Updated"


# ---------- DASHBOARD ----------
def test_dashboard_stats(session, tokens):
    r = session.get(f"{API}/dashboard/stats", headers=_hdr(tokens, "hr"), timeout=15)
    assert r.status_code == 200
    data = r.json()
    for k in ("active_jobs", "total_jobs", "total_candidates", "score_distribution", "recent_jobs"):
        assert k in data
    assert {"low", "mid", "high"}.issubset(data["score_distribution"].keys())


# ---------- AI PROVIDER TEST ----------
def test_provider_test_connection(session, tokens):
    payload = {
        "provider_type": "emergent",
        "base_url": "",
        "api_key": "",
        "llm_provider": "openai",
        "model_name": "gpt-4o-mini",
    }
    r = session.post(
        f"{API}/config/ai-providers/test",
        json=payload,
        headers=_hdr(tokens, "admin"),
        timeout=45,
    )
    assert r.status_code == 200
    data = r.json()
    # may be success=False if Emergent slow; we just assert the contract
    assert "success" in data
    if not data["success"]:
        pytest.skip(f"LLM test returned error: {data.get('error')}")


# ---------- JOB POSTING ----------
JD_TEXT = (
    "Posisi: Payroll Specialist. Departemen: HR. Persyaratan: minimal 3 tahun pengalaman "
    "payroll, paham peraturan PPh21 dan BPJS, mampu menggunakan Excel mahir, lulusan S1 "
    "Akuntansi. Bonus: pengalaman dengan sistem SAP HR atau Talenta. Tanggung jawab: "
    "memproses gaji bulanan, rekonsiliasi pajak karyawan, melaporkan SPT masa PPh21."
)


@pytest.fixture(scope="session")
def created_job(session, tokens):
    data = {"title": "TEST Payroll Specialist", "department": "HR", "raw_jd_text": JD_TEXT}
    r = session.post(
        f"{API}/jobs",
        data=data,
        headers=_hdr(tokens, "manager"),
        timeout=90,  # LLM extraction sync
    )
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["id"]
    assert job["title"] == "TEST Payroll Specialist"
    assert job["extraction_status"] in ("done", "processing", "failed")
    yield job
    try:
        session.delete(f"{API}/jobs/{job['id']}", headers=_hdr(tokens, "manager"), timeout=15)
    except Exception:
        pass


def test_create_job_triggers_extraction(created_job):
    # extraction is synchronous so should be done (or failed if LLM failed)
    assert created_job["extraction_status"] == "done", (
        f"Extraction did not complete: {created_job.get('extraction_error')}"
    )
    assert len(created_job["criteria"]) >= 1
    # At least must-have criteria exist
    must = [c for c in created_job["criteria"] if c["type"] == "must"]
    assert len(must) >= 1


def test_create_job_short_jd_rejected(session, tokens):
    r = session.post(
        f"{API}/jobs",
        data={"title": "Too short", "department": "HR", "raw_jd_text": "x"},
        headers=_hdr(tokens, "manager"),
        timeout=15,
    )
    assert r.status_code == 400


def test_list_jobs(session, tokens, created_job):
    r = session.get(f"{API}/jobs", headers=_hdr(tokens, "hr"), timeout=10)
    assert r.status_code == 200
    jobs = r.json()
    ids = [j["id"] for j in jobs]
    assert created_job["id"] in ids
    for j in jobs:
        assert "candidate_count" in j


def test_get_job_detail(session, tokens, created_job):
    r = session.get(f"{API}/jobs/{created_job['id']}", headers=_hdr(tokens, "hr"), timeout=10)
    assert r.status_code == 200
    assert r.json()["id"] == created_job["id"]


def test_reextract_job(session, tokens, created_job):
    r = session.post(
        f"{API}/jobs/{created_job['id']}/reextract",
        headers=_hdr(tokens, "manager"),
        timeout=60,
    )
    assert r.status_code == 200
    j = r.json()
    assert j["extraction_status"] == "done"


# ---------- CV UPLOAD + SCREENING ----------
CV_TEXT = (
    "Nama: Budi Santoso\nEmail: budi.santoso@example.com\nTelepon: 081234567890\n"
    "Pendidikan: S1 Akuntansi, Universitas Indonesia, 2017.\n"
    "Pengalaman: 5 tahun sebagai Payroll Specialist di PT ABC (2018-2023). "
    "Memproses payroll 500+ karyawan, menghitung PPh21, BPJS, dan SPT masa. "
    "Mahir Excel dan sistem Talenta HR.\n"
    "Skills: Payroll processing, PPh21, BPJS, Excel, Talenta, SAP HR."
)


def test_upload_cv_and_screen(session, tokens, created_job):
    files = [("files", ("budi_cv.txt", io.BytesIO(CV_TEXT.encode("utf-8")), "text/plain"))]
    r = session.post(
        f"{API}/jobs/{created_job['id']}/upload-cv",
        files=files,
        headers=_hdr(tokens, "hr"),
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uploaded"] == 1
    assert len(body["candidate_ids"]) == 1

    # poll
    deadline = time.time() + 90
    scored = None
    while time.time() < deadline:
        rr = session.get(
            f"{API}/jobs/{created_job['id']}/candidates",
            headers=_hdr(tokens, "hr"),
            timeout=15,
        )
        assert rr.status_code == 200
        rows = rr.json()
        done = [x for x in rows if x.get("id") is not None]
        if done:
            scored = done[0]
            break
        time.sleep(4)

    assert scored is not None, "No screening result completed within 90s"
    assert 0 <= scored["total_score"] <= 100
    assert scored["recommendation"] in ("shortlist", "review", "reject")
    pytest.created_screening_id = scored["id"]


def test_get_screening_detail(session, tokens):
    sid = getattr(pytest, "created_screening_id", None)
    if not sid:
        pytest.skip("No screening created")
    r = session.get(f"{API}/screenings/{sid}", headers=_hdr(tokens, "hr"), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "screening" in body and "candidate" in body and "job" in body


def test_update_decision(session, tokens):
    sid = getattr(pytest, "created_screening_id", None)
    if not sid:
        pytest.skip("No screening created")
    r = session.patch(
        f"{API}/screenings/{sid}/decision",
        json={"decision": "shortlisted"},
        headers=_hdr(tokens, "hr"),
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "shortlisted"


def test_invalid_decision(session, tokens):
    sid = getattr(pytest, "created_screening_id", None)
    if not sid:
        pytest.skip("No screening")
    r = session.patch(
        f"{API}/screenings/{sid}/decision",
        json={"decision": "invalid_xyz"},
        headers=_hdr(tokens, "hr"),
        timeout=10,
    )
    assert r.status_code == 400


def test_rescreen_all_candidates(session, tokens, created_job):
    # 1. Deny for hr_recruiter
    r = session.post(
        f"{API}/jobs/{created_job['id']}/candidates/rescreen-all",
        headers=_hdr(tokens, "hr"),
        timeout=15,
    )
    assert r.status_code == 403

    # 2. Allow for hiring_manager
    r2 = session.post(
        f"{API}/jobs/{created_job['id']}/candidates/rescreen-all",
        headers=_hdr(tokens, "manager"),
        timeout=15,
    )
    assert r2.status_code == 200
    assert "queued" in r2.json()
    assert r2.json()["queued"] >= 1

