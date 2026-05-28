# PRD — Sistem Penapisan CV Berbasis AI (Semantic CV Screening)

## Original Problem Statement
"buatkan aplikasi fullstack berdasar PRD Docx terlampir"

PRD uploaded by user: `PRD_Semantic_CV_Screening_v1.0.docx` — internal HR recruitment platform that automates CV screening with semantic AI matching (not keyword matching). Bahasa Indonesia UI.

## Stack Adaptations from PRD (user-approved)
- **PRD says**: PostgreSQL + Next.js + Celery + LiteLLM
- **Implemented**: MongoDB (motor) + React + FastAPI + BackgroundTasks + Emergent Universal LLM Key (via `emergentintegrations.LlmChat`) with custom provider override (admin panel)
- Auth: JWT (HS256) + bcrypt password hashing, 3 roles: hr_recruiter / hiring_manager / admin_it

## User Personas (from PRD §3)
- HR Recruiter — upload JD & CV, see ranking, export
- Hiring Manager — review rationale, decide
- Admin IT — configure AI provider, manage users

## Core Requirements (Static, from PRD)
- JD upload (PDF/DOCX/TXT) + AI extraction → must-have / nice-to-have / experience / education / responsibilities
- CV batch upload (≤500) + AI parsing → structured profile (work history, skills, education, certs)
- Semantic matching across 5 dimensions (must=40, exp=30, domain=15, edu=5, nice=10) with configurable weights & thresholds (shortlist≥75, reject<40)
- Rationale generation in Bahasa Indonesia (strengths, gaps, recommendation)
- RBAC enforcement
- Configurable AI provider (Emergent or OpenAI-compatible)

## Implemented in v1 MVP (2026-05-28)
- ✅ JWT login + /auth/me + RBAC middleware
- ✅ 3 demo accounts seeded idempotently (hr@/manager@/admin@demo.com — `demo123`)
- ✅ JD CRUD: create (file or text), list, detail, re-extract — synchronous LLM extraction on create
- ✅ CV batch upload + async background processing (parse + score + rationale)
- ✅ Ranked candidates table per JD with polling for in-progress items
- ✅ Screening detail page: radar chart (Recharts), 5-dimension breakdown, rationale panel, strengths, gaps, decision actions (shortlist/hold/reject)
- ✅ Admin AI Provider config: list + test connection + add custom OpenAI-compatible provider
- ✅ Admin User management: list + add + activate/deactivate
- ✅ Dashboard stats: active jobs, total candidates, processed today, score distribution (low/mid/high), recent jobs
- ✅ Bahasa Indonesia UI with Swiss/high-contrast design (zinc neutral + emerald/amber/rose for score semantics)
- ✅ data-testid attributes throughout

## Architecture Notes
- Backend: `/app/backend/{server,auth,models,ai_service,file_parser,seed}.py`
- Frontend: `/app/frontend/src/{pages,components,context,lib}/`
- AI calls go through `ai_service.call_llm()` which routes to `LlmChat` with Emergent key OR custom provider
- Background tasks: FastAPI `BackgroundTasks` (per-CV: parse → evaluate → store ScreeningResult)
- MongoDB collections: `users`, `job_postings`, `candidates`, `screening_results`, `ai_provider_configs`

## Test Coverage (iteration_1.json)
- Backend: 21/21 pytest PASS
- Frontend: full e2e validated (login → dashboard → jobs → JD detail → screening detail → admin pages)

## Implemented in v1.1 — Talent Pool (2026-05-28)
- ✅ `GET /api/talent-pool` — all parsed candidates with best score across jobs, screenings count, shortlist count
- ✅ `GET /api/talent-pool/{id}` — candidate detail + full screening history across jobs
- ✅ `POST /api/jobs/{job_id}/screen-from-pool` — re-screen selected candidates (or auto-top-N) against a new JD; skips already-screened pairs
- ✅ `/talent-pool` page with stats (total, high-score, screened, shortlisted) + searchable table
- ✅ `/talent-pool/:id` page with screening history sidebar (clickable to existing ScreeningDetail)
- ✅ "Saran dari Pool" button + dialog in JobDetail with checkbox picker, Top 5/Top 10 quick select

## Deferred / P1 Backlog
- Audit log persistence + audit log viewer page
- Industry ontology editor (admin)
- OCR for scanned/image-based CVs (Tesseract integration)
- PDF export of screening report
- Per-JD weight editing UI (currently only via PATCH /jobs)
- Multiple AI provider profiles with profile switcher in main flow
- Versioning of JD criteria

## P2 Backlog
- Bulk progress indicator for large CV batches
- AES-256 encryption for stored API keys
- Rate limiting middleware
- Backup automation
