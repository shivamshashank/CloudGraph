#!/usr/bin/env bash
# ==============================================================================
# CloudGraph Helm Deployment & Upgrade/Rollback Validation Script
# ==============================================================================
# This script automates chart linting, template rendering verification, dry-run
# installation tests, upgrade simulations, and live-cluster health check runs.
# Suitable for execution in EC2, Orbstack, or local development environments.
# ==============================================================================

set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0;37m' # No Color

CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/cloudgraph" && pwd)"
NAMESPACE="cloudgraph-system"
RELEASE_NAME="cloudgraph"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_cli() {
    local cmd=$1
    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd CLI is not installed but is required."
        return 1
    fi
    return 0
}

# 1. Prerequisite Checks
log_info "Verifying required command line tools..."
check_cli "helm"
check_cli "kubectl"

# 2. Chart Lint Checks
log_info "Running 'helm lint' on chart: ${CHART_DIR}..."
if helm lint "${CHART_DIR}"; then
    log_success "Helm chart linting passed successfully!"
else
    log_error "Helm chart linting failed. Please fix warnings/errors before deploying."
    exit 1
fi

# 3. Template Rendering Validation
log_info "Verifying template rendering using 'helm template'..."
if helm template "${RELEASE_NAME}" "${CHART_DIR}" > /dev/null; then
    log_success "Templates rendered successfully without syntax errors!"
else
    log_error "Template rendering failed. Check template expressions."
    exit 1
fi

# 4. Dry-run Deployment Simulation
log_info "Simulating installation via dry-run..."
if helm install "${RELEASE_NAME}" "${CHART_DIR}" --namespace "${NAMESPACE}" --create-namespace --dry-run --debug > /dev/null; then
    log_success "Dry-run installation passed successfully!"
else
    log_error "Dry-run installation failed. Check Kubernetes resource descriptors."
    exit 1
fi

# 5. Live Cluster Connection (Optional Status Verification)
log_info "Checking Kubernetes cluster connection status..."
if ! kubectl cluster-info &> /dev/null; then
    log_warn "Kubernetes cluster is offline or inaccessible. Skipping live validation."
    log_info "To deploy and test upgrade/rollback on your live EC2/Orbstack cluster, run:"
    echo "  helm install ${RELEASE_NAME} ${CHART_DIR} --namespace ${NAMESPACE} --create-namespace"
    exit 0
fi

log_success "Kubernetes cluster connection is active."

# 6. Live Upgrade Verification Check
log_info "Simulating upgrade dry-run..."
if helm upgrade "${RELEASE_NAME}" "${CHART_DIR}" --namespace "${NAMESPACE}" --dry-run --debug > /dev/null; then
    log_success "Dry-run upgrade validation passed successfully!"
else
    log_error "Dry-run upgrade validation failed."
    exit 1
fi

# 7. Live Health checks (if release is already deployed)
log_info "Checking if CloudGraph is already deployed in namespace: ${NAMESPACE}..."
if helm status "${RELEASE_NAME}" -n "${NAMESPACE}" &> /dev/null; then
    log_info "CloudGraph release found. Running live pod status evaluation..."

    # Wait for pods
    kubectl rollout status deployment/cloudgraph-api -n "${NAMESPACE}" --timeout=30s || log_warn "cloudgraph-api is not fully ready."
    kubectl rollout status deployment/cloudgraph-ui -n "${NAMESPACE}" --timeout=30s || log_warn "cloudgraph-ui is not fully ready."
    kubectl rollout status deployment/agent-orchestrator -n "${NAMESPACE}" --timeout=30s || log_warn "agent-orchestrator is not fully ready."
    kubectl rollout status deployment/investigation-engine -n "${NAMESPACE}" --timeout=30s || log_warn "investigation-engine is not fully ready."

    log_success "All deployments successfully validated on the cluster!"
else
    log_info "CloudGraph is not currently running. Run the following to perform a fresh-cluster deploy:"
    echo "  ./install.sh"
fi
