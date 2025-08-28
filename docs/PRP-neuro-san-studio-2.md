See tools/prps-codex/PRPs/PRP-neuro-san-studio-2.md for the full PRP mirrored into the parent repo.

# Neuro-San Studio 2 — Product Requirements Plan (PRP)

[This document mirrors the PRP stored under tools/prps-codex to ensure it is tracked by the parent repo.]

Version: 0.1 (Draft)
Owner: Legal Discovery Team
Scope: Parent project `nsans-2/neuro-san-studio-2` with emphasis on `apps/legal_discovery`

## Executive Summary

We will elevate Neuro-San Studio 2 to a production-ready, delightful legal discovery experience by:

- Revamping the UI/UX to a polished, 12/10 quality bar grounded in consistent design tokens, fast interactions, and accessible, focused workflows.
- Hardening and verifying all API endpoints for correctness, responsiveness, and predictable error semantics with health checks, SLOs, and observability.
- Fixing ChromaDB failures during document ingestion by isolating ingestion into resilient background jobs, batching writes, adding backpressure, and robust retries.
- Delivering a far smoother, faster document upload and ingestion pipeline with job-based progress, deduplication, chunking, and incremental status updates.

See the canonical version for full sections: goals, current state, requirements (UI/UX, API, ingestion), endpoints inventory, design changes, SLOs, risks, milestones, acceptance criteria, backlog, and open questions.

