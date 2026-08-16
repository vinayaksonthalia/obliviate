"""
Obliviate — FastAPI application.

Exposes the memory engine over a small JSON API and serves the console UI. The `/api/forget`
endpoint returns the full verifiable-erasure bundle (receipt + proof-of-prior-existence via
AS OF SYSTEM TIME + proof-of-absence) in a single response — the heart of the demo.
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingest import ingest_document          # noqa: E402
from core.ask import ask as ask_memory            # noqa: E402
from core.forget import forget, prior_state, verify_gone  # noqa: E402
from db import store                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
STATIC = os.path.join(ROOT, "static")

app = FastAPI(title="Obliviate", description="Verifiable forgetting for AI-agent memory")
if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


class IngestReq(BaseModel):
    subject: str
    title: str = ""
    text: str


class AskReq(BaseModel):
    query: str
    history: list | None = None


class ForgetReq(BaseModel):
    subject: str


@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(TEMPLATES, "index.html")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    return "<h1>Obliviate</h1><p>UI not built yet.</p>"


@app.get("/api/health")
def health():
    return {"ok": True, "service": "obliviate"}


@app.post("/api/ingest")
def api_ingest(r: IngestReq):
    return ingest_document(r.subject, r.title or r.subject, r.text)


@app.post("/api/ask")
def api_ask(r: AskReq):
    return {"answer": ask_memory(r.query, r.history)}


@app.post("/api/forget")
def api_forget(r: ForgetReq):
    """Verifiable erasure: receipt + proof-of-prior-existence (AOST) + proof-of-absence."""
    receipt = forget(r.subject)
    return {
        "receipt": receipt,
        "proof_prior_existence": prior_state(r.subject, receipt["t_before"]),
        "proof_of_absence": verify_gone(r.subject),
    }


@app.get("/api/graph")
def api_graph():
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT id::string, name, type, subjects, (deleted_at IS NOT NULL) FROM nodes"
        )
        nodes = [
            {"id": r[0], "name": r[1], "type": r[2], "subjects": r[3], "deleted": r[4]}
            for r in c.fetchall()
        ]
        c.execute(
            "SELECT source_id::string, target_id::string, relationship FROM edges"
        )
        edges = [{"source": r[0], "target": r[1], "rel": r[2]} for r in c.fetchall()]
    return {"nodes": nodes, "edges": edges}


@app.get("/api/timeline")
def api_timeline():
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT kind, subject, detail, created_at::string FROM timeline "
            "ORDER BY created_at DESC LIMIT 100"
        )
        return [{"kind": r[0], "subject": r[1], "detail": r[2], "at": r[3]} for r in c.fetchall()]


@app.get("/api/events")
def api_events():
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT subject, docs_removed, nodes_removed, edges_removed, nodes_invalidated, "
            "created_at::string FROM erasure_events ORDER BY created_at DESC LIMIT 100"
        )
        return [
            {"subject": r[0], "docs": r[1], "nodes": r[2], "edges": r[3],
             "invalidated": r[4], "at": r[5]}
            for r in c.fetchall()
        ]


@app.get("/api/subjects")
def api_subjects():
    with store.connect() as conn, conn.cursor() as c:
        c.execute("SELECT DISTINCT subject FROM documents ORDER BY subject")
        return [r[0] for r in c.fetchall()]
