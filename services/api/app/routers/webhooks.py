"""Webhook API endpoints."""

from fastapi import APIRouter, HTTPException
from app.schemas import GitCommitPayload, ArgoCDDeploymentPayload
from app.adapters.webhooks import ingest_argocd_deployment, ingest_git_commit
from app.database.redis_client import redis_client
from app.dependencies import semantic_store

router = APIRouter()


@router.post("/api/v1/webhook/git")
def post_git_webhook(payload: GitCommitPayload):
    """Process git webhook payloads and register matching document entry."""
    try:
        result = ingest_git_commit(
            payload.sha,
            payload.author,
            payload.message,
            payload.timestamp,
            payload.changed_files,
        )
        semantic_store.index_document(
            payload.sha,
            (
                f"commit {payload.sha} by {payload.author}: {payload.message}; "
                f"changed files {', '.join(payload.changed_files)}"
            ),
            {
                "type": "commit",
                "label": "Commit",
                "name": payload.sha,
                "author": payload.author,
                "timestamp": payload.timestamp,
            },
        )
        redis_client.clear_cache()
        return {"status": "success", "sha": result[0]["sha"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/webhook/argocd")
def post_argocd_webhook(payload: ArgoCDDeploymentPayload):
    """Process ArgoCD synchronization webhook payload mappings."""
    try:
        result = ingest_argocd_deployment(
            payload.app_name,
            payload.namespace,
            payload.status,
            payload.revision,
            payload.timestamp,
        )
        semantic_store.index_document(
            f"deployment:{payload.app_name}:{payload.revision}",
            (
                f"deployment {payload.app_name} namespace {payload.namespace} "
                f"status {payload.status} revision {payload.revision} "
                f"timestamp {payload.timestamp}"
            ),
            {
                "type": "deployment",
                "label": "Deployment",
                "name": payload.app_name,
                "namespace": payload.namespace,
                "status": payload.status,
                "revision": payload.revision,
                "timestamp": payload.timestamp,
            },
        )
        redis_client.clear_cache()
        return {
            "status": "success",
            "deployment": result[0]["deployment_name"] if result else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
