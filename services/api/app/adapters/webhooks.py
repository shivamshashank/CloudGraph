"""Adapter for processing and ingesting git webhooks into Neo4j."""

from app.database.neo4j_client import neo4j_client


def ingest_git_commit(
    sha: str,
    author: str,
    message: str,
    timestamp: int,
    details: dict | None = None,
):
    """
    Ingests Git commits, mapping changed files and correlating with deployments.
    """
    details = details or {}
    changed_files = details.get("changed_files", [])
    repo_name = details.get("repo_name", "")

    query = """
    MERGE (c:Commit {sha: $sha})
    SET c.author = $author,
        c.message = $message,
        c.timestamp = $timestamp,
        c.changedFiles = $changed_files,
        c.repoName = $repo_name
    WITH c
    OPTIONAL MATCH (d:Deployment)
    WHERE $repo_name <> "" AND (
        toLower(d.name) CONTAINS toLower($repo_name)
        OR toLower($repo_name) CONTAINS toLower(d.name)
    )
    FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
        MERGE (c)-[:TRIGGERED_BY]->(d)
    )
    RETURN c.sha as sha
    """
    params = {
        "sha": sha,
        "author": author,
        "message": message,
        "timestamp": int(timestamp),
        "changed_files": changed_files,
        "repo_name": repo_name,
    }
    return neo4j_client.execute_query(query, params)


def ingest_argocd_deployment(
    app_name: str, namespace: str, status: str, revision: str, timestamp: int
):
    """
    Ingests ArgoCD deployment updates and correlates them with Git commit SHAs.
    """
    query = """
    MERGE (d:Deployment {name: $app_name})
    SET d.namespace = $namespace,
        d.status = $status,
        d.timestamp = $timestamp

    // Relate deployment state to triggering Git commit if indexed
    WITH d
    MATCH (c:Commit {sha: $revision})
    MERGE (c)-[:TRIGGERED_BY]->(d)
    RETURN d.name as deployment_name
    """
    params = {
        "app_name": app_name,
        "namespace": namespace,
        "status": status,
        "revision": revision,
        "timestamp": int(timestamp),
    }
    return neo4j_client.execute_query(query, params)
