# Yield Intelligence

Marketing ROI, budget optimization, and transformation accelerator for CMOs.
FastAPI backend + React frontend, single-container deployment.

---

## What this does

Yield Intelligence turns a client's marketing data into three things:
1. **Current state** — channel-level performance, efficient frontier, attribution
2. **Budget optimization** — MMM response curves + constrained optimizer for optimal allocation
3. **Strategic opportunities** — 94-item catalog of moves, filtered by triggers against the client's data

The product is 7 screens: Executive Summary, Opportunities, Performance, Trust,
Simulate, Plan, Track. Each works at the CMO level (skim) AND the analyst level
(drill, override, defend).

---

## Architecture

```
/
├── frontend/          React + Vite + Tailwind + Recharts + React Query
│   ├── src/
│   │   ├── pages/      Screen components (one per screen)
│   │   ├── components/ TopNav, Atlas chatbot, ScenarioTray, Footer
│   │   ├── api/        Typed API client
│   │   ├── hooks/      useTray (persistent selection across screens)
│   │   └── lib/        Formatting helpers
│   └── dist/           Build output (copied to backend/static for single-container deploy)
├── backend/           FastAPI + SQLAlchemy + PyMC + scipy
│   ├── app/
│   │   ├── main.py         FastAPI entry, serves API + SPA
│   │   ├── api/            Routes, Pydantic schemas
│   │   ├── models/         ORM: campaign, journey, catalog, action, scenario, override, ...
│   │   ├── services/       Exec Summary, Performance, Scenario composers
│   │   ├── triggers/       Opportunity detection engine (12 rules on 94-item catalog)
│   │   ├── mmm/            Bayesian MMM (PyMC 5) + transforms
│   │   ├── attribution/    Markov + Shapley
│   │   ├── optimizer/      Constrained portfolio optimization
│   │   └── data/seed/      Packaged Acme dataset + 94-item catalog + 5 global signal CSVs
│   └── requirements.txt
├── scripts/
│   └── fit_mmm.py      MMM fit CLI (--synthetic for 30s fallback, default for 20-40min Bayesian fit)
├── railway.json        Railway deploy config
├── nixpacks.toml       Build pipeline
└── Procfile            Fallback start command
```

### Stack choices

- **SQLite by default** (works out-of-box). Flip to Postgres by setting `DATABASE_URL`.
- **Single-tenant v1** — one workspace hardcoded (`acme_retail`). Multi-tenancy
  scaffolding is in the data model but disabled for v1.
- **No auth** — deliberately out of scope. Add a reverse proxy / Cloudflare Access
  in front when deploying to production.
- **MMM ships with synthetic fallback** so the product works immediately.
  Run real Bayesian fit post-deploy for proper posteriors.

---

## Run locally

### Prerequisites
- Python 3.11+
- Node 20+

### Setup

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### Development mode (two processes)

```bash
# Terminal 1 — FastAPI on :8000 (seeds DB on first boot)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Vite dev server on :5173 (proxies /v1 to :8000)
cd frontend
npm run dev
```

Open http://localhost:5173. The first boot takes ~15s as it loads 117K journey
touchpoints and 23K campaign rows into SQLite.

### Production mode (single process)

```bash
# Build frontend and copy to backend/static
cd frontend
npm run build
cd ..
mkdir -p backend/static && cp -r frontend/dist/* backend/static/

# Run backend — serves both API and SPA on :8000
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

---

## Deploy to Railway

1. Push this repo to GitHub
2. On Railway: New Project → Deploy from GitHub repo
3. Railway detects `nixpacks.toml` and builds automatically
4. **Upgrade to a paid plan** — PyMC + PyTensor install is ~1.2GB, larger than the free tier
5. First deploy will boot with the synthetic MMM artifact (auto-seeded from packaged Acme data)

### Post-deploy: fit the real MMM

Once deployed, shell into your Railway container and run:

```bash
cd backend
python ../scripts/fit_mmm.py
```

This kicks off a real Bayesian PyMC fit — takes 20-40 minutes depending on container
size. The resulting `mmm_summary.json` artifact is served by the API immediately
after the fit completes. (Until then, the synthetic fallback serves.)

For a quick smoke test first:

```bash
python ../scripts/fit_mmm.py --quick   # ~5-10 min, 200 draws
```

### Environment variables

See `.env.example`. Most important for Railway:

- `DATABASE_URL` — set to the Postgres URL Railway provisions (optional; SQLite
  works for demos)
- `CORS_ORIGINS` — set to your Railway domain
- `ENVIRONMENT=production`

---

## Status of v1

### What works
- [x] Full 7-screen frontend
- [x] Backend: 18 API endpoints, all tested
- [x] 12 trigger rules on the 94-item catalog
- [x] Bayesian MMM code (PyMC 5) with synthetic fallback
- [x] Markov + Shapley attribution (tested on 40K / 15K journeys)
- [x] SLSQP portfolio optimizer
- [x] Scenario composer with overrides + audit trail
- [x] Atlas chatbot (library-driven canned Q&A per screen)
- [x] Responsive UI with Fraunces serif for dollar values, Plus Jakarta for text

### What's deferred
- [ ] Real PyMC fit (run post-deploy; synthetic ships by default)
- [ ] CSV upload endpoint — Acme data packaged for v1
- [ ] Authentication / multi-tenancy — out of v1 scope
- [ ] GA4/Meta/HubSpot connectors — CSV upload path only
- [ ] Plan screen owner/date assignment — placeholder UI in v1
- [ ] Track screen results — populated once a plan has run for a cycle
- [ ] Atlas conversation mode — library-driven only in v1

### Honest known issues
- **Synthetic MMM has near-uniform channel betas** (~$3.8M across all channels
  due to ridge compression on 60 obs). This is documented in code and Trust page
  UI. Real PyMC fit differentiates properly.
- **Startup takes 15-30s first boot** as Acme data loads. Subsequent boots are <1s.
- **ROI trend chart on Exec Summary is synthesized** — backend doesn't yet
  expose time-series. Real implementation is ~30 lines of code in `services/exec_summary.py`.
- **Plan screen owner/date columns are placeholders** — v1 doesn't sync to
  Asana/Jira. Stub cells say "unassigned" / "TBD".

---

## License

Proprietary. See LICENSE if packaged.
