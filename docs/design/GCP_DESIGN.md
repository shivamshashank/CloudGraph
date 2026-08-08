# Graph Confidence Propagation (GCP) Algorithm Design

The Graph Confidence Propagation (GCP) algorithm is a novel graph-neural-inspired propagation technique designed to calculate and propagate belief values across a Kubernetes topological dependency graph. It maps initial local telemetry anomaly confidences to global infrastructure failure probabilities.

## 1. Mathematical Formulation

### 1.1 Initial Confidence Assignment

Evidence/telemetry nodes are assigned an initial confidence $c_0(v) \in [0, 1]$:

* **Metric Anomaly Nodes**: $c_0(m) = 0.80$ (scaled by anomaly severity)
* **Error Log Nodes**: $c_0(l) = 0.85$
* **Security Threat Nodes**: $c_0(s) = 0.90$
* **Deployment Rollout Nodes**: $c_0(d) = 0.75$
* **Commit Regression Nodes**: $c_0(c) = 0.70$
* Other structural nodes start with $c_0(v) = 0.00$.

### 1.2 Edge Propagation & Path Decay

Confidence propagates across directed/undirected relationships in the K8s topology. Every relationship has a configured edge weight $w(e) \in [0, 1]$:

* `GENERATES` (Pod $\rightarrow$ Metric/Log): $w = 0.95$
* `BELONGS_TO` (Pod $\rightarrow$ Service): $w = 0.80$
* `CALLS` (Service $\rightarrow$ Service): $w = 0.75$
* `RUNS_ON` (Pod $\rightarrow$ Node): $w = 0.60$
* `MANAGES` (Deployment $\rightarrow$ Pod): $w = 0.85$
* `UPDATED_BY` / `TRIGGERED_BY` (Deployment $\rightarrow$ Commit): $w = 0.90$

When confidence propagates along a path $P = (v_0, v_1, \dots, v_k)$, it decays exponentially with the path length $k$ using a hop decay factor $\gamma \in [0, 1]$ (default $\gamma = 0.85$):
$$c(P) = c_0(v_0) \times \left( \prod_{i=1}^{k} w(v_{i-1}, v_i) \right) \times \gamma^k$$

### 1.3 Noisy-OR Aggregation

If a node $u$ receives incoming propagated confidences from multiple independent paths $P_1, P_2, \dots, P_m$, they are aggregated using the Noisy-OR probabilistic gate:
$$C(u) = 1 - \prod_{j=1}^{m} (1 - c(P_j))$$

This ensures that multiple weak indicators recursively increase the likelihood of a node being the root cause of an incident.

---

## 2. Pseudocode

```text
Algorithm GraphConfidencePropagation:
    Input: target_pod_name, max_depth, decay_factor (gamma)
    Output: dict of node_id -> confidence_score

    Initialize queue Q
    Initialize map confidence_scores with 0.0 for all nodes
    Initialize map path_confidences with empty list for all nodes

    # Phase 1: Assign initial confidences to telemetry and evidence nodes
    Find all telemetry/evidence nodes connected to target pod within max_depth
    For each evidence node v:
        c_val = assign_initial_confidence(v)
        confidence_scores[v] = c_val
        Q.push((v, c_val, 0)) # (node, current_confidence, depth)

    # Phase 2: Breadth-First Propagation
    While Q is not empty:
        curr_node, curr_conf, curr_depth = Q.pop()

        If curr_depth >= max_depth:
            continue

        For each neighbor u of curr_node:
            edge_w = get_edge_weight(curr_node, u)
            propagated_conf = curr_conf * edge_w * gamma

            If propagated_conf > 0.01:
                path_confidences[u].append(propagated_conf)
                # Recalculate node confidence using Noisy-OR
                old_conf = confidence_scores[u]
                new_conf = 1.0 - Product(1.0 - p for p in path_confidences[u])
                confidence_scores[u] = new_conf

                # If new confidence significantly increases, propagate further
                If new_conf - old_conf > 0.05:
                    Q.push((u, propagated_conf, curr_depth + 1))

    # Phase 3: Write-back results to Neo4j
    For each node, score in confidence_scores:
        write_property_to_node(node, "confidence", score)

    Return confidence_scores
```

---

## 3. Complexity Analysis

* **Space Complexity**: $O(V + E)$ to store graph traversals and path scores.
* **Time Complexity**: $O(V \cdot b^d)$ where:
  * $V$ is the number of nodes in the local subgraph.
  * $b$ is the average branching factor of the topology.
  * $d$ is the maximum propagation depth (`max_depth`).
  Given that $d \le 3$ for Kubernetes microservices, the algorithm executes in sub-millisecond real-time latency.
