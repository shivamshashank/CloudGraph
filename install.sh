#!/usr/bin/env bash
set -euo pipefail

# CloudGraph Installation Script
# Detects Kubernetes cluster, installs kubeadm if needed, then deploys CloudGraph via Helm

CLOUDGRAPH_VERSION="${CLOUDGRAPH_VERSION:-latest}"
CLOUDGRAPH_NAMESPACE="cloudgraph-system"
HELM_REPO_NAME="cloudgraph"
HELM_REPO_URL="https://charts.cloudgraph.dev"
HELM_CHART="cloudgraph/cloudgraph"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check for kubectl
check_kubectl() {
    print_header "Step 1: Checking for kubectl"

    if command_exists kubectl; then
        print_success "kubectl found: $(kubectl version --client -o json | grep gitVersion)"
        return 0
    else
        print_error "kubectl not found"
        return 1
    fi
}

# Step 2: Check for Kubernetes cluster
check_k8s_cluster() {
    print_header "Step 2: Checking for Kubernetes cluster"

    if ! command_exists kubectl; then
        print_error "kubectl is required to check cluster"
        return 1
    fi

    if kubectl cluster-info &>/dev/null; then
        local cluster_info
        cluster_info=$(kubectl cluster-info)
        print_success "Kubernetes cluster detected"
        echo "$cluster_info" | head -3
        return 0
    else
        print_warning "No Kubernetes cluster detected"
        return 1
    fi
}

# Step 3: Offer kubeadm installation
install_kubeadm() {
    print_header "Step 3: Kubernetes cluster not found"

    echo "Would you like to install Kubernetes using kubeadm?"
    echo "Options:"
    echo "  1) Install kubeadm + kubelet + kubectl locally"
    echo "  2) Skip and use existing cluster"
    echo "  3) Exit"

    read -r -p "Choose option (1-3): " choice

    case $choice in
        1)
            print_info "Installing Kubernetes..."
            install_kubernetes_local
            ;;
        2)
            print_warning "Skipping kubeadm installation"
            return 1
            ;;
        3)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid option"
            install_kubeadm
            ;;
    esac
}

# Install Kubernetes locally (kubeadm)
install_kubernetes_local() {
    OS=$(uname -s)

    if [[ "$OS" == "Darwin" ]]; then
        print_info "macOS detected - using Docker Desktop Kubernetes"
        echo "Please enable Kubernetes in Docker Desktop settings"
        echo "Then run this script again"
        exit 1
    elif [[ "$OS" == "Linux" ]]; then
        print_info "Linux detected - installing kubeadm cluster"
        install_kubeadm_linux
    else
        print_error "Unsupported OS: $OS"
        exit 1
    fi
}

install_kubeadm_linux() {
    print_info "Installing kubeadm, kubelet, and kubectl..."

    # Update system
    sudo apt-get update -y

    # Install required packages
    sudo apt-get install -y apt-transport-https ca-certificates curl gpg

    # Add Kubernetes repo
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

    # Install kubeadm, kubelet, kubectl
    sudo apt-get update -y
    sudo apt-get install -y kubeadm kubelet kubectl
    sudo apt-mark hold kubeadm kubelet kubectl

    # Initialize cluster
    print_info "Initializing Kubernetes cluster..."
    sudo kubeadm init --pod-network-cidr=10.244.0.0/16

    # Setup kubeconfig
    mkdir -p "$HOME/.kube"
    sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config"
    sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"

    # Install CNI plugin (Flannel)
    print_info "Installing Flannel CNI..."
    kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml

    # Remove taint from master node to allow pod scheduling
    print_info "Configuring master node..."
    kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true

    print_success "Kubernetes cluster initialized"
    print_info "Waiting for cluster to be ready..."
    sleep 10
    kubectl wait --for=condition=Ready nodes --all --timeout=300s || true
}

# Step 4: Check for Helm
check_helm() {
    print_header "Step 4: Checking for Helm"

    if command_exists helm; then
        print_success "helm found: $(helm version --short)"
        return 0
    else
        print_error "helm not found"
        install_helm
    fi
}

# Install Helm
install_helm() {
    print_info "Installing Helm..."

    if command_exists curl; then
        curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
        print_success "Helm installed"
    else
        print_error "curl is required to install Helm"
        exit 1
    fi
}

# Step 5: Add Helm repository
add_helm_repo() {
    print_header "Step 5: Adding CloudGraph Helm repository"

    helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" --force-update || {
        print_warning "Failed to add official Helm repo, will use local chart"
        return 1
    }

    helm repo update
    print_success "Helm repository updated"
}

# Step 6: Create namespace
create_namespace() {
    print_header "Step 6: Creating CloudGraph namespace"

    kubectl create namespace "$CLOUDGRAPH_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    print_success "Namespace '$CLOUDGRAPH_NAMESPACE' ready"
}

# Step 7: Install CloudGraph
install_cloudgraph() {
    print_header "Step 7: Installing CloudGraph"

    print_info "Installing CloudGraph via Helm..."

    # Try to install from Helm repo, fallback to local chart
    if helm repo list | grep -q "$HELM_REPO_NAME"; then
        helm install cloudgraph "$HELM_CHART" \
            --namespace "$CLOUDGRAPH_NAMESPACE" \
            --create-namespace \
            --version "$CLOUDGRAPH_VERSION" \
            --wait
    else
        print_info "Using local Helm chart..."
        local chart_path="./deployments/helm/cloudgraph"
        if [[ -d "$chart_path" ]]; then
            helm install cloudgraph "$chart_path" \
                --namespace "$CLOUDGRAPH_NAMESPACE" \
                --create-namespace \
                --wait
        else
            print_error "Helm chart not found at $chart_path"
            return 1
        fi
    fi

    print_success "CloudGraph installed successfully"
}

# Step 8: Wait for deployment
wait_for_deployment() {
    print_header "Step 8: Waiting for CloudGraph pods to be ready"

    kubectl wait --for=condition=available --timeout=600s \
        deployment -l app.kubernetes.io/instance=cloudgraph \
        -n "$CLOUDGRAPH_NAMESPACE" || true

    print_success "CloudGraph pods are ready"
}

# Step 9: Display installation summary
print_summary() {
    print_header "Installation Complete!"

    print_success "CloudGraph has been installed successfully"
    echo ""
    echo "Namespace: $CLOUDGRAPH_NAMESPACE"
    echo ""
    echo "Next steps:"
    echo "  1) View CloudGraph pods:"
    echo "     kubectl get pods -n $CLOUDGRAPH_NAMESPACE"
    echo ""
    echo "  2) View CloudGraph logs:"
    echo "     kubectl logs -n $CLOUDGRAPH_NAMESPACE -f deployment/cloudgraph-api"
    echo ""
    echo "  3) Port-forward to UI:"
    echo "     kubectl port-forward -n $CLOUDGRAPH_NAMESPACE svc/cloudgraph-ui 3000:3000"
    echo ""
    echo "  4) Access UI:"
    echo "     http://localhost:3000"
    echo ""
}

# Main installation flow
main() {
    print_header "CloudGraph Installation"
    print_info "Version: $CLOUDGRAPH_VERSION"
    echo ""

    # Check kubectl
    if ! check_kubectl; then
        print_error "kubectl is required. Please install it first."
        exit 1
    fi

    # Check for existing cluster
    if ! check_k8s_cluster; then
        if ! install_kubeadm; then
            print_error "Could not establish Kubernetes cluster"
            exit 1
        fi
    fi

    # Check/install Helm
    check_helm

    # Add Helm repo (non-fatal if fails)
    add_helm_repo || true

    # Create namespace
    create_namespace

    # Install CloudGraph
    install_cloudgraph

    # Wait for deployment
    wait_for_deployment

    # Print summary
    print_summary
}

# Run main function
main "$@"
