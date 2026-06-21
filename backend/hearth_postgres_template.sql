-- ==============================================================================
-- HEARTH - Human Resources Applicant Tracking & CV Screening System
-- PostgreSQL Database Template
-- ==============================================================================
-- File: hearth_postgres_template.sql
-- Deskripsi: Script SQL untuk inisialisasi skema database PostgreSQL
--            dan data awal (seeds) untuk hosting PostgreSQL Anda.
-- ==============================================================================

-- Hapus tabel jika sudah ada (Opsional, untuk instalasi bersih)
DROP TABLE IF EXISTS system_settings CASCADE;
DROP TABLE IF EXISTS ai_search_logs CASCADE;
DROP TABLE IF EXISTS screening_results CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;
DROP TABLE IF EXISTS job_postings CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS ai_provider_configs CASCADE;

-- ==============================================================================
-- 1. TABEL: users
-- Menyimpan informasi pengguna aplikasi (HR Recruiter, Manager, Admin IT)
-- ==============================================================================
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'hr_recruiter' | 'hiring_manager' | 'admin_it'
    is_active BOOLEAN DEFAULT TRUE,
    created_at VARCHAR(50) NOT NULL
);

CREATE INDEX idx_users_email ON users(email);

-- ==============================================================================
-- 2. TABEL: job_postings
-- Menyimpan informasi lowongan pekerjaan dan kriteria penyaringan (screening)
-- ==============================================================================
CREATE TABLE job_postings (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(255) DEFAULT '',
    raw_jd_text TEXT NOT NULL,
    file_name VARCHAR(255),
    target_position VARCHAR(255) DEFAULT '',
    min_experience_years INTEGER DEFAULT 0,
    education_requirement VARCHAR(255) DEFAULT '',
    education_level VARCHAR(50) DEFAULT '',
    education_major VARCHAR(255) DEFAULT '',
    responsibilities JSONB, -- Menggunakan JSONB untuk efisiensi penyimpanan & query di Postgres
    criteria JSONB,
    weights JSONB,
    status VARCHAR(50) DEFAULT 'draft', -- 'draft' | 'active' | 'closed' | 'archived'
    created_by VARCHAR(36) NOT NULL,
    created_at VARCHAR(50) NOT NULL,
    extraction_status VARCHAR(50) DEFAULT 'processing',
    extraction_error TEXT,
    start_date VARCHAR(50),
    end_date VARCHAR(50),
    location VARCHAR(255)
);

CREATE INDEX idx_job_postings_created_by ON job_postings(created_by);
CREATE INDEX idx_job_postings_status ON job_postings(status);

-- ==============================================================================
-- 3. TABEL: candidates
-- Menyimpan data pelamar dan hasil ekstraksi CV oleh AI
-- ==============================================================================
CREATE TABLE candidates (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) DEFAULT 'Unknown',
    email VARCHAR(255) DEFAULT '',
    phone VARCHAR(50) DEFAULT '',
    file_name VARCHAR(255) DEFAULT '',
    raw_text TEXT,
    parsed JSONB,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending' | 'processing' | 'parsed' | 'failed'
    error_message TEXT,
    created_at VARCHAR(50) NOT NULL,
    job_posting_id VARCHAR(36) NOT NULL,
    cv_embedding JSONB -- Opsional untuk integrasi pencarian semantik (semantic search)
);

CREATE INDEX idx_candidates_job_posting ON candidates(job_posting_id);
CREATE INDEX idx_candidates_email ON candidates(email);

-- ==============================================================================
-- 4. TABEL: screening_results
-- Menyimpan hasil penilaian CV kandidat terhadap kriteria lowongan pekerjaan
-- ==============================================================================
CREATE TABLE screening_results (
    id VARCHAR(36) PRIMARY KEY,
    job_posting_id VARCHAR(36) NOT NULL,
    candidate_id VARCHAR(36) NOT NULL,
    total_score INTEGER DEFAULT 0,
    must_have JSONB,
    experience JSONB,
    domain JSONB,
    education JSONB,
    nice_have JSONB,
    recommendation VARCHAR(50) DEFAULT 'review', -- 'shortlist' | 'review' | 'reject'
    rationale_summary TEXT,
    strengths JSONB,
    gaps_summary JSONB,
    decision VARCHAR(50) DEFAULT 'pending', -- 'pending' | 'shortlisted' | 'rejected' | 'hold'
    decided_by VARCHAR(36),
    decided_at VARCHAR(50),
    created_at VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0
);

CREATE INDEX idx_screening_results_job_posting ON screening_results(job_posting_id);
CREATE INDEX idx_screening_results_candidate ON screening_results(candidate_id);
CREATE INDEX idx_screening_results_decision ON screening_results(decision);

-- ==============================================================================
-- 5. TABEL: ai_provider_configs
-- Konfigurasi provider AI / LLM untuk ekstraksi dan penilaian CV
-- ==============================================================================
CREATE TABLE ai_provider_configs (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider_type VARCHAR(50) DEFAULT 'emergent', -- 'emergent' | 'custom'
    base_url VARCHAR(255) DEFAULT '',
    api_key VARCHAR(255) DEFAULT '',
    llm_provider VARCHAR(50) DEFAULT 'anthropic', -- 'anthropic' | 'openai' | 'gemini'
    model_name VARCHAR(50) DEFAULT 'claude-sonnet-4-6',
    temperature REAL DEFAULT 0.2,
    max_tokens INTEGER DEFAULT 4000,
    is_active BOOLEAN DEFAULT TRUE,
    created_at VARCHAR(50) NOT NULL
);

-- ==============================================================================
-- 6. TABEL: system_settings
-- Menyimpan pemetaan provider AI yang aktif untuk fungsi sistem tertentu
-- ==============================================================================
CREATE TABLE system_settings (
    id VARCHAR(50) PRIMARY KEY,
    parsing_provider_id VARCHAR(36) REFERENCES ai_provider_configs(id) ON DELETE SET NULL,
    scoring_provider_id VARCHAR(36) REFERENCES ai_provider_configs(id) ON DELETE SET NULL,
    embeddings_provider_id VARCHAR(36) REFERENCES ai_provider_configs(id) ON DELETE SET NULL
);

-- ==============================================================================
-- 7. TABEL: ai_search_logs
-- Menyimpan log pencarian semantik AI untuk keperluan audit & analisis token
-- ==============================================================================
CREATE TABLE ai_search_logs (
    id VARCHAR(36) PRIMARY KEY,
    query TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at VARCHAR(50) NOT NULL
);


-- ==============================================================================
-- SEED DATA (DATA AWAL UTK OPERASIONAL PERTAMA)
-- ==============================================================================

-- 1. Tambah Akun Demo / Pengguna Default
-- Password hash menggunakan bcrypt untuk pengamanan jika password login sewaktu-waktu diaktifkan kembali.
-- Karena Login konvensional dinonaktifkan demi Google OAuth-only, password hash ini di-set dengan nilai aman acak.
INSERT INTO users (id, name, email, password_hash, role, is_active, created_at)
VALUES 
    (
        'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d', 
        'Hana Recruiter', 
        'hr@demo.com', 
        '$2b$12$K1dJt65eT0G3Nbe6kLsnIeJbH0pXoU/vK7.H0b6f9T17/9X8F1wF6', -- bcrypt hash utk 'demo123'
        'hr_recruiter', 
        TRUE, 
        '2026-05-31T00:00:00Z'
    ),
    (
        'f6e5d4c3-b2a1-0f9e-8d7c-6b5a4f3e2d1c', 
        'Manuel Manager', 
        'manager@demo.com', 
        '$2b$12$K1dJt65eT0G3Nbe6kLsnIeJbH0pXoU/vK7.H0b6f9T17/9X8F1wF6', -- bcrypt hash utk 'demo123'
        'hiring_manager', 
        TRUE, 
        '2026-05-31T00:00:00Z'
    ),
    (
        'c7b8a901-2345-6789-0123-456789abcdef', 
        'Adi Admin IT', 
        'hrdaplzoommeeting@gmail.com', -- Email admin utama sesuai instruksi
        '$2b$12$yK/2o7b7.iVdWhJdC5gVKePsz13kI/7397b91S484F2B72D3.S1d.', -- secure random password hash
        'admin_it', 
        TRUE, 
        '2026-05-31T00:00:00Z'
    )
ON CONFLICT (email) DO NOTHING;

-- 2. Tambah Default AI Provider Config (Emergent Universal)
INSERT INTO ai_provider_configs (id, name, provider_type, base_url, api_key, llm_provider, model_name, temperature, max_tokens, is_active, created_at)
VALUES 
    (
        'd5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a', 
        'Emergent Universal (Default)', 
        'emergent', 
        '', 
        '', 
        'anthropic', 
        'claude-sonnet-4-6', 
        0.2, 
        4000, 
        TRUE, 
        '2026-05-31T00:00:00Z'
    )
ON CONFLICT DO NOTHING;

-- 3. Tambah System Settings Mengacu ke Provider Aktif
INSERT INTO system_settings (id, parsing_provider_id, scoring_provider_id, embeddings_provider_id)
VALUES 
    (
        'default', 
        'd5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a', 
        'd5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a', 
        'd5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a'
    )
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- SELESAI
-- ==============================================================================
