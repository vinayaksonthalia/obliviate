"""
Seed a rich demo knowledge base into Obliviate (default workspace).

An SRE / incident-response memory: ~13 systems as subjects, with runbooks that
cross-reference each other (shared entities like the api-gateway edge, the
core-platform team, Redis) so a Forget & Prove on one subject demonstrates
shared-node *retention* — surviving subjects keep the shared entity, with the
erased subject's provenance removed.

Review dates are backdated so Curation (aging records, memory-health) and the
Timeline have real content. Run:  python scripts/seed_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingest import ingest_document   # noqa: E402
from db import store                       # noqa: E402

WS = "default"

# (subject, title, runbook text, reviewed_days_ago)
CORPUS = [
    ("api-gateway", "api-gateway runbook",
     "The api-gateway is the public entrypoint, owned by the core-platform team. It terminates TLS, "
     "authenticates requests against auth-service, and applies per-client quotas via the rate-limiter "
     "at the edge. On 429 spikes, check the rate-limiter quota configuration before scaling. All "
     "north-south traffic to payments-service and search-index passes through the gateway.", 12),
    ("auth-service", "auth-service runbook",
     "auth-service issues and validates session tokens for the api-gateway. It is owned by the "
     "core-platform team and stores active sessions in session-store (Redis). If login latency is high, "
     "inspect session-store connection-pool saturation and the bounded pool size. A failed auth-service "
     "deploy will surface as 401s at the api-gateway.", 118),
    ("payments-service", "payments-service runbook",
     "payments-service handles charges and refunds, owned by the payments team. It reads and writes "
     "payments-db and caches idempotency keys in redis-cache. Long-running queries against payments-db "
     "during settlement can exhaust the connection pool; check the primary before failing over. It calls "
     "notification-service to send receipts.", 76),
    ("payments-db", "payments-db runbook",
     "payments-db is the primary Postgres-compatible store for payments-service, owned by the payments "
     "team. Watch for long-running queries during nightly settlement and lock contention on the ledger "
     "table. Read replicas serve reporting so the primary stays free for payments-service writes.", 154),
    ("redis-cache", "redis-cache runbook",
     "redis-cache is a shared cache used by payments-service for idempotency keys and by api-gateway for "
     "hot config. Cache-miss storms after a flush can stampede payments-db — warm the cache before peak. "
     "Owned by the core-platform team.", 40),
    ("session-store", "session-store runbook",
     "session-store is the Redis cluster backing auth-service sessions. The bounded connection-pool size "
     "is the usual culprit for login latency. Owned by the core-platform team; shares the Redis operational "
     "playbook with redis-cache.", 83),
    ("search-index", "search-index runbook",
     "search-index powers product search behind the api-gateway, owned by the discovery team. Reindex jobs "
     "run off the payments-db read replica for catalog data. Stale shards cause missing results; trigger a "
     "rebuild and verify against the primary session-store for personalization.", 372),
    ("notification-service", "notification-service runbook",
     "notification-service sends transactional email and push, owned by the growth team. payments-service "
     "calls it for receipts. It relays outbound email through cloud-mailer and tracks bounce rate; a rising "
     "bounce rate usually means cloud-mailer throttling.", 187),
    ("cloud-mailer", "cloud-mailer runbook",
     "cloud-mailer is the outbound email relay used by notification-service, owned by the growth team. On "
     "throttling, drain the outbound spool slowly and check the sender reputation before retrying so the "
     "bounce rate does not climb.", 103),
    ("cdn", "cdn runbook",
     "The cdn fronts static assets and image-resizer output, owned by the core-platform team. Purge on "
     "release; a stale edge cache serves old product images. Origin is the api-gateway for signed URLs.", 258),
    ("rate-limiter", "rate-limiter runbook",
     "The rate-limiter enforces per-client quotas at the api-gateway edge, owned by the core-platform team. "
     "On 429 spikes, check the client quota configuration; a misconfigured quota can throttle payments-service "
     "callbacks and cause retries.", 45),
    ("image-resizer", "image-resizer runbook",
     "image-resizer generates responsive product images served through the cdn, owned by the discovery team. "
     "Long queues mean the worker pool is undersized; scale workers and confirm the cdn is caching the output.", 590),
    ("legacy-cache", "legacy-cache runbook (deprecated)",
     "legacy-cache was the previous caching tier before redis-cache. It is deprecated and being "
     "decommissioned; runbooks that still point on-call at legacy-cache for payments-service are stale and "
     "should be forgotten once redis-cache fully takes over.", 62),
]


def main():
    print("Resetting the default workspace…")
    with store.connect() as conn, conn.cursor() as c:
        for t in ("documents", "nodes", "edges", "erasure_events", "timeline"):
            c.execute(f"DELETE FROM {t} WHERE workspace = %s", (WS,))
        c.execute("DELETE FROM subject_keys WHERE workspace = %s", (WS,))

    for subj, title, text, _ in CORPUS:
        r = ingest_document(subj, title, text, WS)
        print(f"  ingested {subj:22s} -> {r.get('nodes', r)} ")

    # backdate review dates so Curation (aging) + memory-health have real signal
    with store.connect() as conn, conn.cursor() as c:
        for subj, _, _, days in CORPUS:
            c.execute(
                "UPDATE documents SET reviewed_at = now() - (%s || ' days')::INTERVAL "
                "WHERE workspace = %s AND subject = %s",
                (days, WS, subj),
            )
        c.execute("SELECT count(*) FROM documents WHERE workspace=%s", (WS,))
        docs = c.fetchone()[0]
        c.execute("SELECT count(*) FROM nodes WHERE workspace=%s", (WS,))
        nodes = c.fetchone()[0]
        c.execute("SELECT count(*) FROM edges WHERE workspace=%s", (WS,))
        edges = c.fetchone()[0]
    print(f"\nDone. {docs} documents · {nodes} graph nodes · {edges} relationships in '{WS}'.")


if __name__ == "__main__":
    main()
