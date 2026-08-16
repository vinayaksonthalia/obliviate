# Evaluation

Reproduce: `python evals/rrs.py` (runs live against CockroachDB).

## 1. Reconstruction-Robustness Score (RRS)

An attacker holds a leaked/backup copy of a record's ciphertext (as lingers in MVCC history or
backups) and tries to recover the plaintext *after* the record is deleted.

| Deletion method | Records recovered | RRS |
|-----------------|-------------------|-----|
| Naive delete (rows removed, key kept) | **6 / 6** | **0 %** |
| Obliviate (delete + crypto-shred key) | **0 / 6** | **100 %** |

This mirrors *Ghost Vectors* (arXiv:2606.18497): API-deletion leaves data ~99 % recoverable;
destroying the encryption key drops recovery to 0 %.

## 2. Forget-correctness (behavioral)

Ingest six people, hard-forget three, and probe:

| Check | Result |
|-------|--------|
| Forgotten people — identifying data no longer surfaces in answers | **3 / 3** |
| Surviving people — data still answered correctly | **3 / 3** |

## Research grounding

- Naive deletion is ~18 % robust to reconstruction attacks; dependency-graph-aware *layered*
  deletion reaches ~94 % (*ForgetAgent*, IJRASET) — Obliviate implements the layered approach.
- Crypto-shredding drives residual recovery to 0 % (*Ghost Vectors*, arXiv:2606.18497).
