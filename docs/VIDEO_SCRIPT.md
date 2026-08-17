# Obliviate — 3-minute demo video script

Goal: storytelling first, proof on screen, every requirement named. Target ~2:45 so it never
runs long. Everything shown is live and real (judges penalize mocked functionality).

Stack to name on screen in the first 15s + in the README's first screen:
**CockroachDB · Distributed Vector Index · AS OF SYSTEM TIME · Row-level TTL · Amazon S3 (Object Lock) + EC2.**

---

## Scene 1 — The hook (0:00–0:20)
**On screen:** Obliviate landing page hero; then cut to the console.
**Voiceover:**
> "Every agentic-memory project answers the same question — how do agents *remember* more?
> Obliviate answers the one that regulated, production memory actually demands: when memory is
> wrong, poisoned, or legally required to disappear — can you delete it *everywhere*, atomically,
> and *prove* it's gone? On CockroachDB, we can."

## Scene 2 — The problem (0:20–0:40)
**On screen:** a customer-support agent (or SRE agent) with per-customer memory in the graph view.
**Voiceover:**
> "Agents accumulate memory forever. A poisoned fact corrupts every future answer. A departed
> customer's data lingers past its retention window. And in most systems, 'delete' leaves
> recoverable vectors on disk, orphaned graph edges, and no proof anything happened."

## Scene 3 — Build the memory (0:40–1:00)
**On screen:** load demo data / ingest a couple of records; ask a question; get a grounded answer.
**Voiceover:**
> "Obliviate stores an agent's memory as a knowledge graph *and* vectors *and* an audit trail —
> in one CockroachDB store. Watch it answer, grounded strictly in what it knows — and when it
> doesn't know something, it says so. That honesty is what makes forgetting provable."

## Scene 4 — Forget & Prove — THE HERO (1:00–2:10)
**On screen:** click **Forget & Prove** on a subject. The 3 proof cards reveal in sequence.
**Voiceover:**
> "Now erase that customer. One click — and one *atomic* CockroachDB transaction removes their
> documents, graph nodes, edges, and vectors together. Then it proves it, three ways.
>
> **One — it existed.** Using CockroachDB's `AS OF SYSTEM TIME`, we reconstruct exactly what the
> agent knew a moment before erasure. The database's own history *is* the receipt.
>
> **Two — it's gone.** We re-ask the agent about that customer, live — and it now has nothing on
> record. The vector and graph search return nothing. But entities *shared* with other customers
> are kept — erasing one never corrupts another's memory.
>
> **Three — it's irreversible.** Each customer's data is sealed under its own encryption key. We
> destroy that key — so even residual bytes in history or backups are cryptographically
> unrecoverable — and issue a signed, object-locked certificate to S3."
**On screen:** open the Certificate of Erasure page (the signed, print-ready cert).

## Scene 5 — The proof it's real (2:10–2:30)
**On screen:** the eval numbers.
**Voiceover:**
> "This isn't a claim. Naive deletion leaves data one-hundred percent recoverable from a leaked
> copy. Obliviate's crypto-shred: zero. And it's grounded in 2026 research on verifiable deletion."

## Scene 6 — Close (2:30–2:45)
**On screen:** architecture one-liner + the stack badges + logos.
**Voiceover:**
> "Graph, vectors, time-travel proof, and retention — one CockroachDB store, deployed on AWS.
> Obliviate: the first database-native right to be forgotten. Your audit log can lie. MVCC can't."

---

## Shot list / checklist
- [ ] Landing hero (light or dark — pick one and stay consistent)
- [ ] Console: ingest / load demo → grounded answer → the "not on record" honesty beat
- [ ] Forget & Prove: the 3 proof cards animating in
- [ ] Certificate of Erasure page (signed)
- [ ] Graph view showing shared node surviving + forgotten node as a ghost
- [ ] Eval numbers (naive 0% → Obliviate 100%)
- [ ] Stack badges named on screen within the first 15s
- [ ] < 3:00 total, public on YouTube/Vimeo, uploaded early
