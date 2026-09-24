# HHGOA Tier A Backend

Minimal deterministic backend for the TigerGraph Agentic Fraud Investigation Agent challenge.

This implementation is intentionally local-first: it runs with CSV/JSON/Parquet inputs when available and supports an explicit deterministic demo mode. It does not require TigerGraph, an LLM, vector search, or public Kaggle files.

## Quick start

```bash
python -m pip install -r requirements.txt
python scripts/run_all_cases.py --demo --out out --cases cases
python scripts/validate_cases.py cases out
```

For official inputs, place transaction, case-pack, and closed-case files under `data/`, `dataset/`, or `input/`, then run:

```bash
python scripts/run_all_cases.py --out out --cases cases
python scripts/validate_cases.py cases out
python scripts/export_ui_data.py out ../frontend/public/data
```

The runner refuses to claim official results when source data is absent. Demo output is marked with `run_mode: demo` and uses `DEMO-*` IDs.

## Scope

Implemented Tier A: deterministic local graph queries, core detectors, episode/exposure calculation, R1-R10 policy decisions, contract outputs, hard validation, telemetry, and a small read-only FastAPI API. Live TigerGraph, LLM planning, vector search, evidence pause/resume, monitoring, and backtesting are intentionally deferred.
