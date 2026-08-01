# Manual Testing: Failing Services (Bad Pods)

This directory contains utility manifests and scripts to deploy 5 mock microservices (3 in failing states, 2 in healthy states) into your Kubernetes cluster to test CloudGraph's discovery, correlation, and AI diagnostic capabilities.

## The Test Services

| Service | Category | Target State | Failure Type / Reason |
| --- | --- | --- | --- |
| **auth-service** | Core | `CrashLoopBackOff` | Exits with status `1` after printing database timeout errors. |
| **payment-service** | Core | `ImagePullBackOff` | Tries to pull a non-existent container tag `nginx:this-tag-does-not-exist-xyz`. |
| **database-postgres** | Core | `CrashLoopBackOff` | Deploys a postgres container without the required `POSTGRES_PASSWORD` env variable. |
| **frontend-service** | Web | `Running` | Healthy web server container (`nginx:alpine`). |
| **gateway-service** | Web | `Running` | Healthy proxy container (`nginx:alpine`). |

---

## Instructions

### Step 1: Deploy the Test Services

From the root of the repository, execute the self-contained script to apply the services in the `cloudgraph-system` namespace:

```bash
# 1. Make the script executable
chmod +x tests/manual/apply_test_services.sh

# 2. Deploy
./tests/manual/apply_test_services.sh
```

---

### Step 2: Verify the Pod States

Wait 20–30 seconds for the pods to begin pulling images and starting up. Then check their status:

```bash
kubectl get pods -n cloudgraph-system
```

You should see an output similar to this:

```text
NAME                                 READY   STATUS             RESTARTS      AGE
auth-service-75b48bc449-xxxxx        0/1     CrashLoopBackOff   3 (45s ago)   2m
payment-service-856644f77c-xxxxx     0/1     ImagePullBackOff   0             2m
database-postgres-6f45cc7d4d-xxxxx   0/1     CrashLoopBackOff   3 (45s ago)   2m
frontend-service-6d8bbf7c6b-xxxxx    1/1     Running            0             2m
gateway-service-5c4d8b9d6c-xxxxx     1/1     Running            0             2m
```

---

### Step 3: Run CloudGraph Discovery

Once the bad pods are visible in `kubectl`, you can trigger CloudGraph's agent discovery to ingest the new layout into the Neo4j graph:

* **Via the UI:** Open **`http://<your-ip>/`** in your browser and click the **"Discover Cluster"** button.
* **Via the CLI:** Log into your instance and run:

  ```bash
  sudo cloudgraph status
  ```

---

### Step 4: Run AI Diagnostics

* Go to the **AI Diagnosis** tab on the web console UI.
* You will now see the generated `Incident` cards for `auth-service`, `payment-service`, and `database-postgres` displaying the correlated root cause, confidence score, and exact SRE remediation steps!

---

## Cleanup

To dismantle and remove the 5 test services from the cluster, run:

```bash
kubectl delete deployment auth-service payment-service database-postgres frontend-service gateway-service -n cloudgraph-system
kubectl delete service auth-service payment-service database-postgres frontend-service gateway-service -n cloudgraph-system
```
