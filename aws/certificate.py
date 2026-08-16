"""
Erasure certificates — the tamper-evident proof-of-erasure.

For each erasure we build a compact certificate that contains NO personal data (the subject is
hashed), sign it with ECDSA, and — when AWS is configured — write it to an S3 bucket under
Object Lock (WORM / compliance mode) so the receipt itself cannot be altered or deleted.

Without AWS configured the certificate is still built and signed locally, so the proof works in
development; S3 storage activates automatically once credentials are present.
"""
from __future__ import annotations

import os
import json
import base64
import hashlib
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def aws_configured() -> bool:
    return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("S3_CERT_BUCKET"))


def _signing_key():
    pem = os.environ.get("OBLIVIATE_SIGNING_KEY")
    if not pem:
        return None
    return serialization.load_pem_private_key(base64.b64decode(pem), password=None)


def generate_signing_key() -> str:
    """Return a base64 PEM ECDSA private key (store in OBLIVIATE_SIGNING_KEY)."""
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return base64.b64encode(pem).decode()


def public_key_pem() -> str | None:
    key = _signing_key()
    if not key:
        return None
    return key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def issue(receipt: dict, proof_prior: list, proof_absence: dict, issued_at: str) -> dict:
    """Build → sign → (optionally) store an erasure certificate. Returns cert metadata.

    Claims are precise about what erasure guarantees: the subject's source DOCUMENTS are
    encrypted and their key destroyed (content cryptographically unrecoverable); exclusive graph
    entities + edges are deleted; entities shared with surviving subjects are retained for them
    with this subject's provenance removed. We do NOT claim the derived graph text is crypto-shredded.
    """
    workspace = receipt.get("workspace", "default")
    subject_sha = hashlib.sha256(f"{workspace}:{receipt['subject']}".encode()).hexdigest()
    shredded = bool(proof_absence.get("key_shredded"))
    cert = {
        "obliviate_erasure_certificate": "v1",
        "subject_sha256": subject_sha,
        "event_id": receipt["event_id"],
        "t_before": receipt["t_before"],
        "removed": {
            "documents": receipt["docs"],
            "exclusive_nodes": receipt["nodes"],
            "exclusive_edges": receipt["edges"],
            "shared_nodes_retained": receipt["invalidated"],
        },
        "prior_existence_entities": len(proof_prior),
        "guarantees": {
            "document_content_crypto_shredded": shredded,
            "exclusive_graph_deleted": True,
            "subject_provenance_removed_from_shared_nodes": True,
        },
        "issued_at": issued_at,
    }
    body = json.dumps(cert, sort_keys=True, separators=(",", ":")).encode()
    result = {"certificate": cert, "sha256": hashlib.sha256(body).hexdigest(), "stored": False}

    key = _signing_key()
    if key:
        sig = key.sign(body, ec.ECDSA(hashes.SHA256()))
        result["signature"] = base64.b64encode(sig).decode()

    if aws_configured():
        try:
            import boto3

            bucket = os.environ["S3_CERT_BUCKET"]
            s3_key = f"certificates/{subject_sha[:16]}-{receipt['event_id']}.json"
            s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
            s3.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
                ObjectLockMode="COMPLIANCE",
                ObjectLockRetainUntilDate=datetime.now(timezone.utc) + timedelta(days=3650),
                Metadata={"sha256": result["sha256"]},
            )
            result.update(stored=True, s3_bucket=bucket, s3_key=s3_key)
        except Exception as e:  # never let cert storage break the erasure
            result["store_error"] = str(e)[:200]

    return result
