# SimpleATS

SimpleATS is a small Applicant Tracking System (ATS) starter project containing a Python backend and a React frontend.

## Contents
- `backend/` — Python service and API
- `frontend/` — React app and UI components

## Quickstart

Prerequisites:
- Python 3.8+ (backend)
- Node.js 14+ and Yarn or npm (frontend)

Backend (development):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# run the server (example)
python server.py
```

Frontend (development):

```bash
cd frontend
# using yarn
yarn install
yarn start
# or using npm
npm install
npm start
```

## Environment
This repository contains example `.env` files under `backend/.env` and `frontend/.env`. These files may contain sensitive values (API keys, secrets). Do NOT commit real secrets.

If you accidentally committed secrets, remove them from the history before sharing the repo publicly. I can help remove them using `git filter-repo` or BFG.

## Git
Repository has been pushed to: https://github.com/Indragunwan/SimpleATS.git

## Next steps
- Verify and move any real secrets out of `.env` and into secure storage.
- Add setup scripts or dockerization if you want reproducible dev environments.

## Sumopod LLM provider (example)

You can use Sumopod (or another HTTP-based LLM provider) with the project's
pluggable `call_llm` by supplying an async `llm_client` and API key via
`config`.

Two options:

1) Manual config (inline):

```python
from backend.llm_clients import sumopod_llm_client

config = {
	"llm_client": sumopod_llm_client,
	"api_key": "YOUR_SUMOPOD_KEY",
	"base_url": "https://ai.sumopod.com",
	"endpoint": "/v1/chat",
	"api_key_header": "Authorization",
	"api_key_value_prefix": "Bearer ",
}

# call any ai_service function, e.g.:
await extract_jd_criteria(jd_text, config=config)
```

2) Load from environment (recommended for local dev):

Create `backend/.env` with:

```
SUMOPOD_API_KEY=your_key_here
SUMOPOD_BASE_URL=https://ai.sumopod.com
```

Then use the helper:

```python
from backend.llm_utils import get_sumopod_config_from_env

config = get_sumopod_config_from_env()
await extract_jd_criteria(jd_text, config=config)
```

Make sure `backend/.env` is listed in `.gitignore` (do NOT commit real keys).

---
If you want, I can expand this README with detailed API docs, example env values, or Docker instructions.

