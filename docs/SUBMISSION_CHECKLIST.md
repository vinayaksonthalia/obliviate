# Submission Checklist — CockroachDB × AWS "Build with Agentic Memory"

Deadline: **Aug 18, 2026, 5:00pm EDT**. This maps every rule to our deliverable.

## Required deliverables
- [ ] **Public code repository** with an OSI license — repo `vinayaksonthalia/obliviate`
      (private during build; **flip to public before submitting**). ✅ **MIT** license committed.
- [ ] **Functional demo app URL** — deployed on AWS (EC2 + S3), reachable by judges.
- [ ] **Text description** of features & functionality (Devpost fields + README).
- [ ] **Demo video < 3 minutes**, public on YouTube/Vimeo, **showing the CockroachDB memory
      layer at work** (ingest → ask → forget → 3-part proof).
- [ ] **Tool documentation** — which CockroachDB tools and AWS services we use, and how (below).
- [ ] Optional: architecture diagram (have one) + feedback on CockroachDB tooling.

## Challenge requirements
- [x] **≥ 2 CockroachDB capabilities, meaningfully integrated** — we use **five**:
  1. **Distributed Vector Indexing (C-SPANN)** — semantic recall + the "search returns nothing"
     erasure proof (verified index-backed, not full-scan — see `docs/SMOKE_TESTS.md`).
  2. **`AS OF SYSTEM TIME`** time-travel — the proof-of-prior-existence receipt.
  3. **Serializable transactions** — the cascade delete + invalidate + crypto-shred all commit or none do.
  4. **Recursive CTEs** — exhaustive blast-radius traversal of the knowledge graph.
  5. **Row-level TTL** — retention/decay enforcement.
  - **MCP-native:** Obliviate ships its own MCP server (FastMCP) backed by CockroachDB, so any MCP
    agent (Claude Desktop/Code, Cursor) can remember, recall, and provably forget through the same store.
- [x] **≥ 1 AWS service** — **Amazon S3** (object-locked / WORM erasure certificates) + **EC2**
      (hosting the deployed app). Erasure certificates are signed **in-process** with ECDSA (P-256).
- [ ] **Newly created during the submission period** — new repo, new CockroachDB-native codebase.
- [ ] All materials in **English**.

## Judging criteria — how we score
| Criterion | Our answer |
|-----------|-----------|
| Agentic Memory Design | CockroachDB is the memory layer: graph + vectors + proof + TTL in one ACID store. |
| Technical Implementation | Index-backed ANN, recursive-CTE cascade, envelope encryption + crypto-shred. |
| Real-World Impact | GDPR/HIPAA right-to-erasure — a board-level blocker for regulated AI deployments. |
| Product Readiness | Auth, XSS-safe UI, tamper-evident S3 certificates, observability, tests. |
| Creativity & Originality | The only entry whose thesis is *provable forgetting*, backed by 2026 research. |

## Pre-submission gate
- [ ] Repo public + README + setup instructions + architecture diagram
- [ ] Live demo URL verified reachable
- [ ] Video uploaded (public) and linked
- [ ] Devpost form: tools used, AWS services, repo, demo, video
- [ ] `EXPLAIN` query-plan receipt + eval numbers in README
