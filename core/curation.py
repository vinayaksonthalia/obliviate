"""
Curation — keep memory current between hard erasures.

Three tools, cheapest first:
  * demote / restore  — reversible down-weighting of a subject's nodes (soft-forget); the record
    stays but stops surfacing. The opposite pole from forget()'s irreversible hard delete.
  * stale_references  — after an entity is erased, find surviving nodes/edges whose text still
    *mentions* it (graph hygiene — a lingering reference the hard delete didn't reach).
  * aging_documents   — records not reviewed in a while, candidates for retention review; the
    engine-enforced row-level TTL is the automatic backstop.
"""
from __future__ import annotations

from db import store

NEUTRAL_WEIGHT = 0.5
DEMOTE_MILD = 0.25
DEMOTE_DEEP = 0.05


def demote(subject: str, weight: float = DEMOTE_DEEP) -> int:
    """Reversibly down-weight a subject's nodes so they stop surfacing (record retained)."""
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "UPDATE nodes SET weight = %s WHERE %s::STRING = ANY(subjects) AND deleted_at IS NULL",
            (weight, subject),
        )
        n = c.rowcount
        c.execute(
            "INSERT INTO timeline (kind, subject, detail) VALUES ('demote', %s, %s)",
            (subject, f"demoted {subject} to weight {weight} ({n} nodes) — reversible"),
        )
    return n


def restore(subject: str) -> int:
    """Undo a demote: back to neutral weight."""
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "UPDATE nodes SET weight = %s WHERE %s::STRING = ANY(subjects) AND deleted_at IS NULL",
            (NEUTRAL_WEIGHT, subject),
        )
        n = c.rowcount
        c.execute(
            "INSERT INTO timeline (kind, subject, detail) VALUES ('restore', %s, %s)",
            (subject, f"restored {subject} to neutral weight ({n} nodes)"),
        )
    return n


def stale_references(subject: str | None = None) -> list[dict]:
    """Surviving nodes/edges whose text still mentions an already-erased subject."""
    with store.connect() as conn, conn.cursor() as c:
        if subject:
            erased = [subject]
        else:
            c.execute("SELECT DISTINCT subject FROM erasure_events")
            erased = [r[0] for r in c.fetchall()]
        hits: list[dict] = []
        for subj in erased:
            like = f"%{subj}%"
            c.execute(
                "SELECT name, description FROM nodes "
                "WHERE deleted_at IS NULL AND description ILIKE %s",
                (like,),
            )
            hits += [{"kind": "node", "where": r[0], "mentions": subj, "text": r[1]} for r in c.fetchall()]
            c.execute(
                "SELECT relationship, description FROM edges WHERE description ILIKE %s", (like,)
            )
            hits += [{"kind": "edge", "where": r[0], "mentions": subj, "text": r[1]} for r in c.fetchall()]
        return hits


def aging_documents(days: int = 180) -> list[dict]:
    """Documents not reviewed within `days` — retention-review candidates (row-level TTL backstops)."""
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT subject, title, reviewed_at::string, "
            "(now()::date - reviewed_at::date) AS age_days "
            "FROM documents WHERE deleted_at IS NULL "
            "AND reviewed_at < now() - ((%s)::string || ' days')::interval "
            "ORDER BY reviewed_at",
            (days,),
        )
        return [{"subject": r[0], "title": r[1], "reviewed_at": r[2], "age_days": r[3]} for r in c.fetchall()]
