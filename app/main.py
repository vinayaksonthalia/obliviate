"""
Obliviate — FastAPI application.

Exposes the memory engine over a small JSON API and serves the console + landing UI.
Every operation is scoped to a WORKSPACE (multi-tenant isolation; defaults to 'default').
`/api/forget` returns the full verifiable-erasure bundle (receipt + AS OF SYSTEM TIME
proof-of-prior-existence + proof-of-absence + signed certificate) in one response.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import FastAPI, UploadFile, File, Form, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingest import ingest_document          # noqa: E402
from core.ask import ask as ask_memory            # noqa: E402
from core.forget import forget, prior_state, verify_gone  # noqa: E402
from core import curation                         # noqa: E402
from llm import client as llm_client              # noqa: E402
from aws import certificate as cert               # noqa: E402
from db import store                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
STATIC = os.path.join(ROOT, "static")

app = FastAPI(title="Obliviate", description="Verifiable forgetting for AI-agent memory")
if os.path.isdir(STATIC):
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _ws(workspace: str | None) -> str:
    """Resolve a workspace id — fail-closed to 'default' only on empty input."""
    return (workspace or "default").strip() or "default"


# ── access control (opt-in via env; off by default for the demo) ──
AUTH_TOKEN = os.environ.get("OBLIVIATE_AUTH_TOKEN")
LOCK_MODEL = os.environ.get("OBLIVIATE_LOCK_MODEL") == "1"


def require_auth(authorization: str | None = Header(None)):
    """If OBLIVIATE_AUTH_TOKEN is set, mutating routes require `Authorization: Bearer <token>`."""
    if AUTH_TOKEN and authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


def _validate_endpoint(url: str) -> None:
    """SSRF guard for a user-supplied LLM endpoint: block private/internal hosts, require https off-box."""
    if not url:
        return
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise HTTPException(status_code=400, detail="invalid endpoint")
    host = p.hostname
    if host in ("localhost", "127.0.0.1", "::1"):
        return
    if p.scheme != "https":
        raise HTTPException(status_code=400, detail="non-local endpoint must use https")
    try:
        for res in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(res[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise HTTPException(status_code=400, detail="endpoint resolves to a non-public address")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="endpoint host could not be resolved")


# ─────────────────────────────────────────────────────────── pages
def _serve(name: str, fallback: str | None = None) -> str:
    path = os.path.join(TEMPLATES, name)
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    if fallback:
        return _serve(fallback)
    return "<h1>Obliviate</h1><p>UI not built yet.</p>"


@app.get("/", response_class=HTMLResponse)
def landing():
    return _serve("landing.html", fallback="index.html")


@app.get("/app", response_class=HTMLResponse)
def console():
    return _serve("index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "obliviate"}


# ─────────────────────────────────────────────────────────── workspaces
class WsReq(BaseModel):
    name: str


class WsDelReq(BaseModel):
    id: str


@app.get("/api/workspaces")
def workspaces_list():
    with store.connect() as conn, conn.cursor() as c:
        c.execute("SELECT id, name FROM workspaces ORDER BY created_at")
        rows = [{"id": r[0], "name": r[1]} for r in c.fetchall()]
    if not any(w["id"] == "default" for w in rows):
        rows = [{"id": "default", "name": "Default"}] + rows
    return rows


@app.post("/api/workspaces")
def workspaces_create(r: WsReq):
    wid = "ws-" + uuid.uuid4().hex[:8]
    name = (r.name or "Untitled").strip()[:80]
    with store.connect() as conn, conn.cursor() as c:
        c.execute("INSERT INTO workspaces (id, name) VALUES (%s, %s)", (wid, name))
    return {"id": wid, "name": name}


@app.post("/api/workspaces/delete")
def workspaces_delete(r: WsDelReq, _: None = Depends(require_auth)):
    if r.id == "default":
        return {"ok": False, "error": "the default workspace cannot be deleted"}
    with store.connect() as conn:
        with conn.transaction():
            with conn.cursor() as c:
                for t in ("edges", "nodes", "documents", "subject_keys", "erasure_events", "timeline"):
                    c.execute(f"DELETE FROM {t} WHERE workspace = %s", (r.id,))
                c.execute("DELETE FROM workspaces WHERE id = %s", (r.id,))
    return {"ok": True, "deleted": r.id}


# ─────────────────────────────────────────────────────────── memory
class IngestReq(BaseModel):
    subject: str
    title: str = ""
    text: str
    workspace: str = "default"


class AskReq(BaseModel):
    query: str
    history: list | None = None
    workspace: str = "default"


class ForgetReq(BaseModel):
    subject: str
    workspace: str = "default"


@app.post("/api/ingest")
def api_ingest(r: IngestReq, _: None = Depends(require_auth)):
    try:
        return ingest_document(r.subject, r.title or r.subject, r.text, _ws(r.workspace))
    except store.KeyDestroyed:
        raise HTTPException(status_code=409,
                            detail="this subject was permanently erased; the name cannot be re-onboarded")


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), subject: str = Form(""),
                     workspace: str = Form("default"), _: None = Depends(require_auth)):
    raw = (await file.read()).decode("utf-8", errors="ignore")
    subj = (subject or os.path.splitext(file.filename or "uploaded")[0])[:80]
    try:
        return ingest_document(subj, file.filename or subj, raw, _ws(workspace))
    except store.KeyDestroyed:
        raise HTTPException(status_code=409,
                            detail="this subject was permanently erased; the name cannot be re-onboarded")


@app.post("/api/ask")
def api_ask(r: AskReq):
    return {"answer": ask_memory(r.query, r.history, _ws(r.workspace))}


@app.post("/api/forget")
def api_forget(r: ForgetReq, _: None = Depends(require_auth)):
    ws = _ws(r.workspace)
    receipt = forget(r.subject, ws)
    prior = prior_state(r.subject, receipt["t_before"], ws)
    absence = verify_gone(r.subject, ws)
    certificate = cert.issue(receipt, prior, absence, datetime.now(timezone.utc).isoformat())
    return {
        "receipt": receipt,
        "proof_prior_existence": prior,
        "proof_of_absence": absence,
        "certificate": certificate,
    }


# ─────────────────────────────────────────────────────────── views
@app.get("/api/graph")
def api_graph(workspace: str = "default"):
    ws = _ws(workspace)
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT id::string, name, type, subjects, (deleted_at IS NOT NULL) "
            "FROM nodes WHERE workspace = %s",
            (ws,),
        )
        nodes = [{"id": r[0], "name": r[1], "type": r[2], "subjects": r[3], "deleted": r[4]}
                 for r in c.fetchall()]
        c.execute(
            "SELECT source_id::string, target_id::string, relationship FROM edges WHERE workspace = %s",
            (ws,),
        )
        edges = [{"source": r[0], "target": r[1], "rel": r[2]} for r in c.fetchall()]
    return {"nodes": nodes, "edges": edges}


@app.get("/api/timeline")
def api_timeline(workspace: str = "default"):
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT kind, subject, detail, created_at::string FROM timeline "
            "WHERE workspace = %s ORDER BY created_at DESC LIMIT 100",
            (_ws(workspace),),
        )
        return [{"kind": r[0], "subject": r[1], "detail": r[2], "at": r[3]} for r in c.fetchall()]


@app.get("/api/events")
def api_events(workspace: str = "default"):
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT id::string, subject, docs_removed, nodes_removed, edges_removed, "
            "nodes_invalidated, created_at::string FROM erasure_events "
            "WHERE workspace = %s ORDER BY created_at DESC LIMIT 100",
            (_ws(workspace),),
        )
        return [{"id": r[0], "subject": r[1], "docs": r[2], "nodes": r[3], "edges": r[4],
                 "invalidated": r[5], "at": r[6]} for r in c.fetchall()]


@app.get("/api/subjects")
def api_subjects(workspace: str = "default"):
    with store.connect() as conn, conn.cursor() as c:
        c.execute("SELECT DISTINCT subject FROM documents WHERE workspace = %s ORDER BY subject",
                  (_ws(workspace),))
        return [r[0] for r in c.fetchall()]


# ─────────────────────────────────────────────────────────── curation
class DemoteReq(BaseModel):
    subject: str
    weight: float | None = None
    workspace: str = "default"


@app.post("/api/demote")
def api_demote(r: DemoteReq):
    return {"demoted_nodes": curation.demote(r.subject, r.weight or curation.DEMOTE_DEEP, _ws(r.workspace))}


@app.post("/api/restore")
def api_restore(r: DemoteReq):
    return {"restored_nodes": curation.restore(r.subject, _ws(r.workspace))}


@app.get("/api/curation")
def api_curation(workspace: str = "default"):
    ws = _ws(workspace)
    return {"stale_references": curation.stale_references(workspace=ws),
            "aging": curation.aging_documents(workspace=ws)}


# ─────────────────────────────────────────────────────────── model (BYO)
class ModelReq(BaseModel):
    provider: str | None = None
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = None


@app.get("/api/model")
def api_model_get():
    return {"provider": llm_client.LLM_PROVIDER, "model": llm_client.LLM_MODEL,
            "endpoint": llm_client.LLM_ENDPOINT}


@app.post("/api/model")
def api_model_set(r: ModelReq, _: None = Depends(require_auth)):
    if LOCK_MODEL:
        raise HTTPException(status_code=403, detail="the model is locked on this deployment")
    _validate_endpoint(r.endpoint or "")
    return llm_client.set_config(r.provider, r.model, r.endpoint, r.api_key)


# ─────────────────────────────────────────────────────────── certificate page
@app.get("/certificate/{event_id}", response_class=HTMLResponse)
def certificate_page(event_id: str):
    with store.connect() as conn, conn.cursor() as c:
        c.execute(
            "SELECT workspace, subject, t_before, docs_removed, nodes_removed, edges_removed, "
            "nodes_invalidated, created_at::string FROM erasure_events WHERE id = %s",
            (event_id,),
        )
        row = c.fetchone()
    if not row:
        return HTMLResponse("<h1>Certificate not found</h1>", status_code=404)
    import hashlib
    subj_hash = hashlib.sha256((row[0] + ":" + (row[1] or "")).encode()).hexdigest()
    fields = {"event_id": event_id, "subject_sha256": subj_hash, "t_before": str(row[2]),
              "documents": row[3], "nodes": row[4], "edges": row[5],
              "shared_invalidated": row[6], "issued_at": row[7]}
    pub = cert.public_key_pem()
    rows_html = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in fields.items()
    )
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>Obliviate — Certificate of Erasure</title>
<style>body{{font-family:ui-monospace,Menlo,monospace;max-width:720px;margin:48px auto;padding:0 20px;color:#0b0b0f}}
h1{{font-family:Georgia,serif;font-weight:600}} table{{width:100%;border-collapse:collapse;margin:20px 0}}
td{{padding:8px 10px;border-bottom:1px solid #e5e5ea}} td:first-child{{color:#6b7280;width:40%}}
.badge{{display:inline-block;background:#0b0b0f;color:#fff;padding:4px 10px;border-radius:6px;font-size:12px}}
@media print{{.noprint{{display:none}}}}</style></head><body>
<div class=badge>OBLIVIATE · CERTIFICATE OF ERASURE</div>
<h1>Verifiable erasure receipt</h1>
<p>This certifies that the subject below was erased from agent memory in one atomic transaction —
documents, graph nodes, edges, and vectors — and its encryption key crypto-shredded, rendering
any residual data cryptographically unrecoverable. The subject is identified by hash (no personal
data is retained in this certificate).</p>
<table>{rows_html}</table>
<p style="color:#6b7280;font-size:13px">Tamper-evidence: this receipt is derived from the
database's own audit record; erasures are additionally signed with an ECDSA key
{'and stored in object-locked (WORM) S3' if cert.aws_configured() else '(local signing)'}.</p>
<button class=noprint onclick=print()>Print / Save as PDF</button>
</body></html>"""
