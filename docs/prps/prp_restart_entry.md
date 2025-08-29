name: "PRP Entry — Legal Discovery Sync (Restart)"
description: |
  Quick restart note capturing current state, recent changes, and next steps
  so the assistant can resume work seamlessly.

---

## Goal

- Ensure the app builds/launches cleanly on Windows (Vite + Docker compose).
- Confirm new graph enrichment, orchestrator passes, and voice settings work end‑to‑end.
- Continue UI polish: live pipeline details, graph path tracing and styling.

## Why

- Recent changes span graph, voice, orchestration, and UI; this entry preserves context
  to avoid re-discovery on next session.

## Current State (Key Changes)

- Graph enrichment patterns added: CAUSES (Facts & Events), OCCURS_BEFORE, SAME_TRANSACTION,
  plus RELATED_TO, CO_SUPPORTS, TEMPORALLY_NEAR, EVIDENCES.
- Endpoints:
  - POST /api/graph/sync_timeline — upsert SQL timeline to Neo4j + stitch edges
  - POST /api/graph/enrich — run enrichers, return deltas
  - GET /api/graph/analyze — centrality + meta.timeline (chain length, 3-hop count)
- Orchestrator: auto 3-pass run after ingestion; emits pipeline_pass and publishes bus topics.
- Voice: engine/model persisted; GET /api/chat/voices and POST /api/chat/voice/settings.
- UI:
  - GraphSection: Analyze / Sync Timeline / Enrich; edge styling + legend; CAUSES path tracing; node click picker
  - PipelineSection: live pipeline_pass listener; Pass Details modal

## Setup (Windows)

1) PowerShell at repo root:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Clean`
2) App: `http://localhost:8080`
3) Logs: `docker compose logs -f legal_discovery`

If Vite build fails with tokens.css or duplicate refs:
- Ensure branch `feat/m3-graph-causation-deltas` is pulled.
- Confirm `apps/legal_discovery/src/tokens.css` exists.

## Sanity Checks

- Graph:
  - POST `/api/graph/sync_timeline`, then `/api/graph/enrich`
  - GET `/api/graph/analyze` → expect `meta.timeline`
  - In UI Graph tab: Analyze / Sync / Enrich; trace a CAUSES path via node clicks + IDs
- Pipeline:
  - Upload docs; watch “Recent Analysis Passes”; open “Details”
- Voice:
  - In Settings: set engine/model; “List Voices” to populate choices

## Next Steps

- UI polish: tabbed modal sections (Deltas | Timeline | Theories | Raw), copy-to-clipboard
- Graph: tooltips for weights, path stepping controls, export path
- Pipeline: persist pass summaries in DB, filter by case/iteration

## Validation Loop

- Frontend: `cd apps/legal_discovery && npm ci && npm run build`
- Backend (Docker): `docker compose build && docker compose up -d`
- Health: `GET /api/health` should report ok for neo4j/chroma/postgres/redis

