"""Webhook API endpoints."""

import time

from fastapi import APIRouter, HTTPException
from app.schemas import GitCommitPayload, ArgoCDDeploymentPayload
from app.adapters.webhooks import ingest_argocd_deployment, ingest_git_commit
from app.dependencies import semantic_store

router = APIRouter()


def _ingest_single_github_commit(
    commit_info: dict, repo_name: str, pusher_name: str
) -> str | None:
    """Helper to process and index a single GitHub commit."""
    sha = commit_info.get("id") or commit_info.get("sha")
    if not sha:
        return None

    author_obj = commit_info.get("author") or {}
    author = author_obj.get("name") or pusher_name or "github-user"
    message = commit_info.get("message", "GitHub webhook push")

    added = commit_info.get("added") or []
    modified = commit_info.get("modified") or []
    removed = commit_info.get("removed") or []
    changed_files = list(dict.fromkeys(added + modified + removed))

    timestamp = int(time.time())

    ingest_git_commit(
        sha=sha,
        author=author,
        message=message,
        timestamp=timestamp,
        details={"changed_files": changed_files, "repo_name": repo_name},
    )

    semantic_store.index_document(
        sha,
        (
            f"github commit {sha[:8]} in repository '{repo_name}' "
            f"by {author}: {message}; changed files: {', '.join(changed_files)}"
        ),
        {
            "type": "commit",
            "label": "Commit",
            "name": sha,
            "author": author,
            "repository": repo_name,
            "timestamp": timestamp,
        },
    )
    return sha


@router.post("/api/v1/webhook/git")
def post_git_webhook(payload: GitCommitPayload):
    """Process git webhook payloads and register matching document entry."""
    try:
        result = ingest_git_commit(
            payload.sha,
            payload.author,
            payload.message,
            payload.timestamp,
            details={"changed_files": payload.changed_files},
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
        return {
            "status": "success",
            "deployment": result[0]["deployment_name"] if result else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/webhook/github")
@router.post("/api/v1/webhooks/github")
def post_github_webhook(payload: dict):
    """Process raw GitHub push event webhooks into graph and vector store."""
    try:
        repo_name = payload.get("repository", {}).get("name", "")
        commits_data = payload.get("commits", [])
        pusher_name = payload.get("pusher", {}).get("name", "github-user")

        if not commits_data and payload.get("head_commit"):
            commits_data = [payload["head_commit"]]

        ingested_shas = []
        for c in commits_data:
            sha = _ingest_single_github_commit(c, repo_name, pusher_name)
            if sha:
                ingested_shas.append(sha)

        return {
            "status": "success",
            "repository": repo_name,
            "commits_ingested": len(ingested_shas),
            "shas": ingested_shas,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
