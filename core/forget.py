"""
Forget: verifiable, atomic erasure of an entity from memory.

The whole operation is ONE serializable CockroachDB transaction:
  1. anchor the pre-deletion moment with cluster_logical_timestamp() (the AS OF SYSTEM TIME proof),
  2. hard-delete the entity's SUBJECT-EXCLUSIVE knowledge — documents, graph nodes, and every
     edge touching them,
  3. INVALIDATE (not delete) SHARED nodes — entities that also belong to a surviving subject stay,
     with the erased subject removed from their provenance, so no other subject's memory is corrupted,
  4. crypto-shred the subject's data key, making any residual ciphertext (MVCC history, backups, S3)
     cryptographically unrecoverable,
  5. record a measured, tamper-evident erasure event.

Because deletion, invalidation, and shred all commit together, memory is never left in a half-erased
state — and the AS OF SYSTEM TIME anchor lets us prove, afterwards, exactly what existed before.
"""
from __future__ import annotations

from db import store


def forget(subject: str, workspace: str = "default") -> dict:
    """Erase `subject` from a workspace's memory. Returns a measured receipt."""
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cluster_logical_timestamp()::string")
            t_before = cur.fetchone()[0]

        receipt = {"docs": 0, "nodes": 0, "edges": 0, "invalidated": 0}

        with conn.transaction():
            with conn.cursor() as cur:
                # subject-exclusive nodes: subject is present AND is the ONLY distinct subject
                cur.execute(
                    """
                    SELECT id FROM nodes
                    WHERE workspace = %s
                      AND %s::STRING = ANY(subjects)
                      AND array_length(array_remove(subjects, %s::STRING), 1) IS NULL
                      AND deleted_at IS NULL
                    """,
                    (workspace, subject, subject),
                )
                exclusive = [r[0] for r in cur.fetchall()]

                if exclusive:
                    cur.execute(
                        "DELETE FROM edges WHERE workspace = %s AND (source_id = ANY(%s) OR target_id = ANY(%s))",
                        (workspace, exclusive, exclusive),
                    )
                    receipt["edges"] = cur.rowcount
                    cur.execute("DELETE FROM nodes WHERE id = ANY(%s)", (exclusive,))
                    receipt["nodes"] = cur.rowcount

                # shared nodes: keep for surviving subjects, remove the erased subject from provenance
                cur.execute(
                    """
                    UPDATE nodes
                    SET subjects = array_remove(subjects, %s::STRING)
                    WHERE workspace = %s
                      AND %s::STRING = ANY(subjects)
                      AND array_length(array_remove(subjects, %s::STRING), 1) >= 1
                      AND deleted_at IS NULL
                    """,
                    (subject, workspace, subject, subject),
                )
                receipt["invalidated"] = cur.rowcount

                # the subject's documents
                cur.execute("DELETE FROM documents WHERE workspace = %s AND subject = %s", (workspace, subject))
                receipt["docs"] = cur.rowcount

                # crypto-shred: destroy the subject's data key
                store.crypto_shred(conn, workspace, subject)

                # measured, tamper-evident erasure event
                cur.execute(
                    """
                    INSERT INTO erasure_events
                      (workspace, subject, t_before, docs_removed, nodes_removed, edges_removed, nodes_invalidated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (workspace, subject, t_before, receipt["docs"], receipt["nodes"],
                     receipt["edges"], receipt["invalidated"]),
                )
                event_id = cur.fetchone()[0]

                cur.execute(
                    "INSERT INTO timeline (workspace, kind, subject, detail) VALUES (%s, 'forget', %s, %s)",
                    (workspace, subject,
                     f"erased {subject}: {receipt['nodes']} nodes, {receipt['edges']} edges, "
                     f"{receipt['docs']} docs deleted; {receipt['invalidated']} shared nodes retained; "
                     f"key crypto-shredded"),
                )

    return {"subject": subject, "workspace": workspace, "t_before": t_before,
            "event_id": str(event_id), **receipt}


def prior_state(subject: str, t_before: str, workspace: str = "default") -> list[dict]:
    """Proof-of-prior-existence: reconstruct what the graph knew about `subject` just before erasure,
    via AS OF SYSTEM TIME. Returns the nodes that existed then. (AOST timestamp must be a literal.)"""
    with store.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT name, type, description FROM nodes AS OF SYSTEM TIME {t_before} "
            "WHERE workspace = %s AND %s::STRING = ANY(subjects)",
            (workspace, subject),
        )
        return [{"name": r[0], "type": r[1], "description": r[2]} for r in cur.fetchall()]


def verify_gone(subject: str, workspace: str = "default") -> dict:
    """Proof-of-absence: after erasure, the subject's exclusive knowledge and key are gone."""
    with store.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM nodes WHERE workspace = %s AND %s::STRING = ANY(subjects) "
            "AND deleted_at IS NULL",
            (workspace, subject),
        )
        live_nodes = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM documents WHERE workspace = %s AND subject = %s", (workspace, subject))
        live_docs = cur.fetchone()[0]
        cur.execute(
            "SELECT wrapped_dek IS NULL, destroyed_at IS NOT NULL FROM subject_keys "
            "WHERE workspace = %s AND subject = %s",
            (workspace, subject),
        )
        row = cur.fetchone()
        key_shredded = bool(row and row[0] and row[1])
    return {"live_exclusive_nodes": live_nodes, "live_docs": live_docs, "key_shredded": key_shredded}
