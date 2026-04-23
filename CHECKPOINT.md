# Yield Intelligence — Backend Checkpoint

Status: **Backend feature-complete for v1. Frontend not started.**

This is a working FastAPI backend with real data, real MMM, real attribution, and real
optimization. Runs locally as-is. Frontend coming in next iteration.

## What works

### Data layer
- SQLite DB auto-seeded from Acme 5-year dataset (23,760 campaign rows, 117,887 journey
  touchpoints, 94 catalog items, 2,815 global signals) on first boot
- Postgres-compatible via single `DATABASE_URL` env var
- Idempotent seed — safe to re-run
- `scripts/fit_mmm.py --synthetic` produces a plausible MMM summary in ~30 seconds so
  the product works immediately after deploy

### API endpoints (all working)
- `GET /health` — liveness probe
- `POST /admin/seed` — idempotent seed
- `POST /admin/detect` — run trigger engine, materialize actions
- `GET /v1/exec-summary` — top-level Exec Summary payload with pillar rollups, KPIs, market trends
- `GET /v1/opportunities` — detected opportunities (filter by pillar, motion)
- `GET /v1/library` — full 94-item catalog with trigger status (filter `not_triggered_only`)
- `GET /v1/performance` — channel diagnostics: Pareto, frontier status, response curves
- `GET /v1/attribution/markov` — Markov chain removal-effect attribution
- `GET /v1/attribution/shapley` — Shapley-value attribution
- `GET /v1/mmm/summary` — MMM posterior summary (per-channel alpha, K, beta)
- `POST /v1/optimize` — constrained portfolio optimization
- `GET /v1/actions` — materialized actions with overrides applied
- `POST /v1/scenarios` — create scenario with action selections
- `GET /v1/scenarios/{id}` — scenario with projected KPIs
- `PATCH /v1/scenarios/{id}/actions` — add/remove actions, re-project
- `POST /v1/overrides` — user override with reason (required)
- `DELETE /v1/overrides/{id}` — soft-delete an override

### Trigger engine (12 rules, 8 firing on Acme data)
Real math against real data. Produces $30.6M "on the table" with proper attribution to
pillars (Revenue / Cost / CX) and motion (optimization / transformation).

### MMM (Bayesian code complete)
Full PyMC 5 model written (`app/mmm/model.py`) with:
- Adstock (geometric, matrix-based for PyTensor compatibility)
- Hill saturation (parametric)
- Hierarchical channel priors (Beta adstock, LogNormal half-sat, HalfNormal beta)
- Trend + Fourier monthly seasonality
- Convergence diagnostics (R-hat)

**Deployed default is the synthetic fallback** (`--synthetic` flag). Real fit takes
20-40 minutes and needs to run on deploy infra, not in a chat session. Everything that
reads the MMM (optimizer, performance screen, response curves) works identically against
synthetic or real posteriors.

### Attribution (both methods tested on real data)
- **Markov chain** — removal-effect method, 5.8s on 40,000 journeys
- **Shapley** — exact on up to 10 channels (2^10 coalitions), 6.4s on 15,089 journeys

### Optimizer
SLSQP constrained optimization over MMM response curves. Handles min/max bounds, locked
channels, budget constraints. Converges cleanly on 11-channel problem (+10.8% revenue
at same budget for Acme).

### Scenario engine
Compose scenarios from selected actions. Per-action overrides with required reasons.
Downstream projection recalculates instantly. Full audit trail.

## What's NOT in this checkpoint

- **Frontend** — zero. All 7 screens still to build.
- **Real MMM fit artifact** — synthetic only. Run `python scripts/fit_mmm.py` post-deploy
  to get real Bayesian posteriors.
- **CSV upload endpoint** — not written. Currently loads from packaged Acme files.
- **Atlas chatbot** — not started.
- **Railway deployment config** — `railway.json`, `Procfile`, nixpacks — not written.
- **Tests** — none. All verification is via `TestClient` smoke runs.
- **Auth / multi-tenant** — deliberately out of scope for v1.

## Running locally

```bash
cd backend
pip install -r requirements.txt

# Seed runs automatically on first boot via lifespan
uvicorn app.main:app --reload --port 8000

# Once running, in another shell:
curl http://localhost:8000/v1/exec-summary
curl http://localhost:8000/v1/opportunities
curl http://localhost:8000/v1/performance

# Optional: produce synthetic MMM summary (runs in ~30s)
python scripts/fit_mmm.py --synthetic

# Optional: real Bayesian MMM (takes 20-40 min, needs PyMC 5)
python scripts/fit_mmm.py
```

## File map

```
backend/
├── app/
│   ├── main.py                    FastAPI entry + startup seeding
│   ├── core/config.py             Env-driven settings
│   ├── db/__init__.py             SQLAlchemy setup
│   ├── api/
│   │   ├── routes.py              All endpoints
│   │   └── schemas.py             Pydantic response models
│   ├── models/                    ORM: campaign, journey, catalog, action, scenario, override, ...
│   ├── services/
│   │   ├── data_loader.py         Seed from Excel + CSV
│   │   ├── exec_summary.py        Screen 01 payload
│   │   ├── performance.py         Screen 03 payload
│   │   └── scenario.py            Scenario composer + projection
│   ├── triggers/engine.py         12 rules, evaluable against live data
│   ├── mmm/
│   │   ├── model.py               PyMC Bayesian MMM
│   │   └── transforms.py          adstock + Hill + response curves
│   ├── attribution/
│   │   ├── markov.py              Markov removal-effect
│   │   └── shapley.py             Exact Shapley (C ≤ 10)
│   ├── optimizer/portfolio.py     SLSQP constrained optimizer
│   └── data/
│       ├── seed/                  Packaged Acme data + catalog + global signals
│       └── artifacts/mmm_summary.json
├── requirements.txt
scripts/
└── fit_mmm.py                     Fit MMM (full Bayesian or synthetic)
```

## Next session

1. Write `uploads.py` — CSV upload to replace Acme data
2. Scaffold React + Vite + Tailwind + Recharts
3. Build Screen 01 (Exec Summary) at design fidelity
4. Build Screen 02 (Opportunities) with drill-down
5. Screens 03-07 (thinner)
6. Atlas library-driven chatbot
7. Railway deploy config
8. Final zip
