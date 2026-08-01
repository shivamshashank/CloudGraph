#!/usr/bin/env bash
set -euo pipefail

echo "Applying Kubernetes test services (3 bad, 2 good)..."

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: cloudgraph-system
---
# 1. auth-service (Bad State: CrashLoopBackOff via Exit 1)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
        - name: auth
          image: busybox:latest
          command: ["sh", "-c", "echo 'Initializing Auth service...'; sleep 5; echo 'Fatal database connection failure!'; exit 1"]
---
apiVersion: v1
kind: Service
metadata:
  name: auth-service
  namespace: cloudgraph-system
spec:
  ports:
    - port: 8083
      targetPort: 8083
  selector:
    app: auth-service
---
# 2. payment-service (Bad State: ImagePullBackOff via Non-Existent Image)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: payment-service
  template:
    metadata:
      labels:
        app: payment-service
    spec:
      containers:
        - name: payment
          image: nginx:this-tag-does-not-exist-xyz
---
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: cloudgraph-system
spec:
  ports:
    - port: 8084
      targetPort: 80
  selector:
    app: payment-service
---
# 3. database-postgres (Bad State: CrashLoopBackOff via Missing Environment Variable)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: database-postgres
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: database-postgres
  template:
    metadata:
      labels:
        app: database-postgres
    spec:
      containers:
        - name: postgres
          image: postgres:15-alpine
          # Leaving out POSTGRES_PASSWORD makes the container crash immediately on startup
---
apiVersion: v1
kind: Service
metadata:
  name: database-postgres
  namespace: cloudgraph-system
spec:
  ports:
    - port: 5432
      targetPort: 5432
  selector:
    app: database-postgres
---
# 4. frontend-service (Good State: Running successfully)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend-service
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend-service
  template:
    metadata:
      labels:
        app: frontend-service
    spec:
      containers:
        - name: frontend
          image: nginx:alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: cloudgraph-system
spec:
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: frontend-service
---
# 5. gateway-service (Good State: Running successfully)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway-service
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gateway-service
  template:
    metadata:
      labels:
        app: gateway-service
    spec:
      containers:
        - name: gateway
          image: nginx:alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: gateway-service
  namespace: cloudgraph-system
spec:
  ports:
    - port: 80
      targetPort: 80
  selector:
    app: gateway-service
EOF

echo "=========================================================="
echo "✓ Applied 5 test services (3 bad, 2 good) in namespace 'cloudgraph-system'."
echo "=========================================================="
echo "Bad Services:"
echo " 1. auth-service        -> CrashLoopBackOff (exits with status 1)"
echo " 2. payment-service     -> ImagePullBackOff (uses non-existent tag)"
echo " 3. database-postgres   -> CrashLoopBackOff (missing POSTGRES_PASSWORD env)"
echo ""
echo "Good Services:"
echo " 4. frontend-service    -> Running (nginx:alpine)"
echo " 5. gateway-service     -> Running (nginx:alpine)"
echo "=========================================================="
echo "You can check their status using:"
echo "  kubectl get pods -n cloudgraph-system"
echo ""
echo "Once running/failing, run 'sudo cloudgraph status' or trigger cluster discovery."
echo "=========================================================="
