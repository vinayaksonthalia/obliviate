# Obliviate

**Verifiable "Right to Be Forgotten" for AI-agent memory — CockroachDB-native.**

Obliviate gives an AI agent's long-term memory a *provable* delete button. Ask it to forget an
entity and it hard-deletes that entity's entire knowledge sub-graph — documents, graph nodes,
edges, and vectors — in one ACID transaction, then **proves it's gone three ways**:

1. **It existed** — CockroachDB `AS OF SYSTEM TIME` reconstructs the pre-deletion state.
2. **It's gone** — live vector + graph search return nothing; the agent answers "not documented."
3. **It's irreversible** — a per-subject encryption key is destroyed (crypto-shred) and a
   signed, object-locked S3 certificate is issued, so residual bytes are unrecoverable.

Built for the **CockroachDB × AWS "Build with Agentic Memory"** hackathon.

## Why CockroachDB (load-bearing, not a checkbox)
- **Graph + vectors + proof in ONE transactional store** (replaces a separate graph DB + vector DB).
- **Forget = one ACID transaction** across documents/nodes/edges/vectors — no multi-store drift.
- **`AS OF SYSTEM TIME`** = the deletion receipt, with no separate audit log.
- **C-SPANN vector index** for semantic recall; **recursive CTE** for exhaustive blast-radius.
- **Row-level TTL** for retention/decay. **Managed MCP Server** for agent memory access.

## Stack
FastAPI · CockroachDB Basic · fastembed (bge-small, 384-d) · Ollama (dev) / hosted LLM (deploy) ·
AWS Lambda + S3 · MCP.

## Status
🚧 In active development. See `../BUILD_PLAN.md` for the full spec and milestones.

## License
MIT
