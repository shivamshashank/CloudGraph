from app.database.neo4j_client import neo4j_client


def ingest_git_commit(
    sha: str, author: str, message: str, timestamp: int, changed_files: list
):
    """
    Ingests Git commits, mapping changed files to index downstream configurations.
    """
    query = """
    MERGE (c:Commit {sha: $sha})
    SET c.author = $author,
        c.message = $message,
        c.timestamp = $timestamp,
        c.changedFiles = $changed_files
    RETURN c.sha as sha
    """
    params = {
        "sha": sha,
        "author": author,
        "message": message,
        "timestamp": int(timestamp),
        "changed_files": changed_files,
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
