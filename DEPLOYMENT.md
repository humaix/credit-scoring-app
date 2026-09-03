# Deployment Guide

How to deploy the **Alternative Credit Scoring** prototype end to end:

| Piece | Platform | What runs there |
|---|---|---|
| FastAPI backend + ML / explainability engine | [Render](https://render.com) | the API, the saved XGBoost pipeline (SHAP scoring), PDF generation |
| Next.js frontend | [Vercel](https://vercel.com) | the applicant-facing UI; talks to the backend over HTTPS |

Everything needed ships with the repository — the model pickle in `models/` is
committed, and both requirements files pin exact tested versions. Secrets are
never committed; they are entered in the platform dashboards.

## Prerequisites

- This repository pushed to GitHub (the `.env` file is gitignored and must
  never be pushed).
- A Render account and a Vercel account (free tiers are enough).
- Optional: an OpenAI-compatible LLM API key (OpenRouter, OpenAI, DashScope…).
  Without one the system still works — every report is worded by the
  deterministic SHAP fallback templates.

## 1. Backend on Render

### Option A — Blueprint (recommended)

1. Render Dashboard → **New → Blueprint**, select the repository.
2. Render reads [`render.yaml`](render.yaml) and creates one web service
   (`credit-scoring-api`). When prompted, provide values for the secret
   variables (all can be changed later under *Environment*):
   - `CORS_ORIGINS` — enter any placeholder for now; the real Vercel URL is
     set in step 3.
   - `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` — your LLM settings, or
     leave `LLM_MODEL` empty to disable the wording layer entirely (no network
     calls are made; fallback templates word every report).
3. **Apply** and wait for the build (~3–5 min). Note the service URL, e.g.
   `https://credit-scoring-api.onrender.com`.

### Option B — manual web service

| Setting | Value |
|---|---|
| Runtime | Python |
| Build command | `pip install -r requirements-api.txt -r requirements-explainability.txt` |
| Start command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |

Then add the environment variables from the reference table below.

> Python version: set `PYTHON_VERSION=3.10.11` (the model pickle was built and
> tested with 3.10.11). If Render rejects that exact patch version, use the
> closest 3.10.x it offers.

## 2. Frontend on Vercel

1. Vercel → **Add New → Project**, import the same GitHub repository.
2. Set **Root Directory** to `frontend` (the Next.js project auto-detects).
3. Add the environment variable (for **Production** and **Preview**):
   - `NEXT_PUBLIC_API_BASE_URL` = your Render service URL, e.g.
     `https://credit-scoring-api.onrender.com` (no trailing slash)
4. **Deploy**. Note the URL, e.g.
   `https://alternative-credit-scoring.vercel.app`.

There is no hard-coded backend URL in production: `frontend/lib/api.ts` only
falls back to `http://localhost:8000` when the variable is unset (local dev).

## 3. Wire them together (CORS)

1. On Render, set `CORS_ORIGINS` to your Vercel URL(s) — comma-separated, no
   trailing slash, e.g.
   `https://alternative-credit-scoring.vercel.app`.
   Include the `*.vercel.app` preview URL too if you want previews to work.
2. Save (Render redeploys automatically when environment variables change).

## 4. Verify the deployment

1. `GET https://<render-service>.onrender.com/api/health` →
   `{"status": "ok"}`.
2. Open the Vercel URL and walk the full flow: register → new application →
   simulated OTP (returned in the API response, clearly labelled) → consent →
   12-question financial behaviour assessment → score with explanation and
   downloadable PDF.
3. The results page shows the score disclaimer; the PDF contains the same
   disclaimer.
4. If LLM keys were set, results show *“AI wording layer”* and the PDF has
   richer wording; otherwise *“Standard templates”*. Both paths are fully
   functional.
5. Spin-down note: free-tier Render services sleep after ~15 minutes of
   inactivity; the first request after sleep takes ~30–60 s to wake the
   service.

## Data persistence

- With the default SQLite, the database is a file on the instance disk.
  **Render's free-tier disk is ephemeral** — demo data is lost when the
  service redeploys or restarts. For a hackathon demo this is fine (users
  simply register again; nothing sensitive is lost).
- For a persistent database: create a Render PostgreSQL instance (or use
  Supabase/Neon) and set `DATABASE_URL` to
  `postgresql+psycopg2://<user>:<password>@<host>/<database>`.
  The driver (`psycopg2-binary`) is already included in
  `requirements-api.txt`, and the schema is created automatically on startup.
- Generated PDF reports also live on the instance disk (regenerated
  automatically from the persisted assessment if missing).

## Local development

```powershell
# backend (Python 3.10) — from the repository root
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-api.txt -r requirements-explainability.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# frontend — second terminal
cd frontend
npm install
npm run dev        # http://localhost:3000 → talks to localhost:8000

# tests
python -m pytest backend/tests -q               # 148 tests
python explainability/test_explainability.py    # 64 checks
```

Copy `.env.example` to `.env` (repository root) to configure LLM access
locally — optional; the fallback templates cover every failure mode.

## Environment variable reference

| Variable | Set where | Required | Default | Purpose |
|---|---|---|---|---|
| `PYTHON_VERSION` | Render | yes | — | `3.10.11` — must match the model pickle's Python |
| `CORS_ORIGINS` | Render / local | yes in production | `http://localhost:3000,http://127.0.0.1:3000` | comma-separated allowed browser origins (your Vercel URL) |
| `DEV_RETURN_OTP` | Render / local | no | `true` | demo mode: simulated OTP returned in responses, clearly labelled. Set `false` if a real SMS gateway is ever attached. |
| `LLM_API_KEY` | Render / `.env` | no | empty | API key for the OpenAI-compatible wording endpoint |
| `LLM_BASE_URL` | Render / `.env` | no | `https://api.openai.com/v1` | e.g. `https://openrouter.ai/api/v1`, DashScope compatible-mode URL |
| `LLM_MODEL` | Render / `.env` | no | empty | model name; **empty disables the LLM** (fallback templates, zero network calls) |
| `LLM_TIMEOUT` | Render / `.env` | no | `30` | LLM request timeout in seconds |
| `DATABASE_URL` | Render / local | no | SQLite file in repo root | switch to `postgresql+psycopg2://…` for a persistent database |
| `OTP_TTL_SECONDS` | Render / local | no | `300` | simulated OTP expiry |
| `OTP_MAX_ATTEMPTS` | Render / local | no | `5` | wrong-OTP attempts before lockout |
| `APP_BASE_URL` | Render / local | no | `http://localhost:3000` | frontend origin used to build password-reset links |
| `RESET_TOKEN_TTL_MINUTES` | Render / local | no | `30` | how long a password-reset link stays valid |
| `DEV_SHOW_RESET_LINK` | Render / local | no | `true` | demo mode: with SMTP unset, the reset link is returned in the API response (clearly labelled) so the flow can be demoed without a mail server. **Never set together with SMTP credentials.** |
| `SMTP_HOST` | Render / `.env` | no | empty | outgoing mail server for password-reset emails; empty disables sending |
| `SMTP_PORT` | Render / `.env` | no | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | Render / `.env` | no | empty | SMTP username |
| `SMTP_PASSWORD` | Render / `.env` | no | empty | SMTP password / app password — secret, never commit |
| `SMTP_FROM` | Render / `.env` | no | `SMTP_USER` | sender address shown on reset emails |
| `UPLOADS_DIR` | Render / local | no | `uploads/` in repo root | where applicant CNIC images are stored (instance disk; see persistence note) |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel / local | yes in production | `http://localhost:8000` | backend base URL used by the frontend |

## Deployment safety notes

- `.env` (with real keys) is gitignored — never commit or push it; secrets
  belong only in the platform dashboards.
- All provider integrations (identity verification, OTP, wallet/telecom
  features) are clearly-labelled simulations — no real NADRA, Easypaisa,
  JazzCash or telecom systems are contacted in any deployment.
- The score is always accompanied by the disclaimer: it is a model-estimated
  repayment assessment, not a guaranteed probability of repayment or a loan
  decision.
