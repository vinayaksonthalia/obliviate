# Obliviate — Development Log

A running, honest engineering log (in the spirit of Lethe's `learning/` docs + `DEEP_DIVE.md`).
Newest entries at the top.

---

## 2026-08-16 — Day 0: foundation

**What Obliviate is:** verifiable "right to be forgotten" for AI-agent memory, CockroachDB-native.
A CockroachDB-native rebuild + extension of the verifiable-forgetting concept proven in the
prior award-winning on-call-memory project (which ran on Cognee + Kùzu + LanceDB).

**Decisions made today:**
- **Engine = CockroachDB-native, no Cognee.** Cognee would bury CockroachDB behind its own
  abstraction (its graph stays in Kùzu), failing the hackathon's #1 criterion and killing the
  "forget = one ACID transaction / AOST receipt / recursive-CTE blast-radius" story. We reuse
  the UI, prompts, curation logic, MCP tool defs, and eval harness; we rebuild the storage layer.
- **Lead vertical = GDPR / personal-data erasure** (life-admin doc set already loaded). Engine
  is entity-agnostic, so SRE/on-call remains a secondary proof point.
- **Stack:** FastAPI · CockroachDB Basic · fastembed bge-small (384-d) · Ollama (dev)
  / hosted LLM, BYO-model (deploy) · Amazon S3 (Object Lock) + EC2 · own MCP server (FastMCP).
- **New vs the prior project:** crypto-shred + object-locked S3 certificate, exhaustive BFS
  blast-radius (recursive CTE), deterministic entity dedup (`INSERT … ON CONFLICT`), AOST
  time-travel receipts, greyed-out forgotten-node "shadows", RBAC.

**Infra provisioned:**
- CockroachDB Basic cluster `obliviate` on **AWS Mumbai (ap-south-1)**, cluster id
  `0c59b7a3-0638-498b-bb54-0b45d75b6615`. Unlimited capacity, $400 trial credits, no card = $0.
- CA cert downloaded to `~/.postgresql/root.crt`.
- GitHub repo `vinayaksonthalia/obliviate` (private → public at submission). Scaffold pushed.

**Next:**
- [x] **Smoke tests — 11/11 PASS** (see `SMOKE_TESTS.md`). Vector index ON by default on Basic,
      cosine ANN is index-backed (lookup join, NOT full scan), AOST + recursive CTE + row-level
      TTL + ON CONFLICT dedup all work. **All technical risk cleared. GO.**
- [ ] Schema + storage layer (documents / nodes / edges / vectors / subject_keys).
- [ ] Port ingest / ask / forget from prior project onto CockroachDB.
- [x] Ship an MCP server (FastMCP) over CockroachDB so agents can remember/recall/forget.
- [x] AWS creds → S3 (Object Lock / WORM) for certificates; certificates signed in-process (ECDSA P-256).
