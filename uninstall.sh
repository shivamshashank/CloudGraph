#!/usr/bin/env bash
set -euo pipefail

# CloudGraph Uninstallation Script
# Safely uninstalls CloudGraph Helm release, deletes namespace, and optionally resets kubeadm

CLOUDGRAPH_NAMESPACE="cloudgraph-system"

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

# Step 1: Uninstall CloudGraph Helm Release
uninstall_helm_release() {
    print_header "Step 1: Uninstalling CloudGraph Helm Release"

    if command_exists helm; then
        if helm list -n "$CLOUDGRAPH_NAMESPACE" | grep -q "cloudgraph"; then
            print_info "Uninstalling Helm release 'cloudgraph' from namespace '$CLOUDGRAPH_NAMESPACE'..."
            helm uninstall cloudgraph -n "$CLOUDGRAPH_NAMESPACE"
            print_success "Helm release uninstalled successfully"
        else
            print_warning "No Helm release named 'cloudgraph' found in namespace '$CLOUDGRAPH_NAMESPACE'"
        fi
    else
        print_warning "Helm is not installed, skipping Helm release uninstallation"
    fi
}

# Step 2: Delete CloudGraph Namespace
delete_namespace() {
    print_header "Step 2: Deleting CloudGraph Namespace"

    if command_exists kubectl; then
        if kubectl get namespace "$CLOUDGRAPH_NAMESPACE" &>/dev/null; then
            print_info "Deleting namespace '$CLOUDGRAPH_NAMESPACE' (this deletes all PVs, PVCs, secrets, and pods)..."
            kubectl delete namespace "$CLOUDGRAPH_NAMESPACE" --timeout=300s
            print_success "Namespace '$CLOUDGRAPH_NAMESPACE' deleted successfully"
        else
            print_warning "Namespace '$CLOUDGRAPH_NAMESPACE' does not exist"
        fi
    else
        print_warning "kubectl is not installed, skipping namespace deletion"
    fi
}

# Step 3: Optional Kubeadm Cluster Reset
reset_kubeadm_cluster() {
    print_header "Step 3: Optional Kubernetes Cluster Reset"

    if ! command_exists kubeadm; then
        print_info "kubeadm is not installed, skipping cluster reset options"
        return 0
    fi

    echo "Would you like to reset and dismantle the local Kubernetes cluster (kubeadm)?"
    echo -e "${RED}WARNING: This will completely destroy the local cluster and stop all running pods!${NC}"
    echo "Options:"
    echo "  1) Reset kubeadm cluster and purge configurations (Keep binaries)"
    echo "  2) Reset kubeadm cluster + Purge all Kubernetes binaries (kubeadm, kubelet, kubectl, containerd, helm)"
    echo "  3) Keep Kubernetes cluster (Only uninstall CloudGraph)"

    read -r -p "Choose option (1-3): " choice

    case $choice in
        1)
            print_info "Resetting kubeadm cluster..."
            sudo kubeadm reset -f || true
            sudo rm -rf ~/.kube
            sudo rm -rf /etc/kubernetes/
            sudo rm -rf /var/lib/etcd/
            sudo rm -rf /var/lib/kubelet/
            sudo rm -rf /var/lib/dockershim/ || true
            sudo rm -rf /var/run/kubernetes/ || true

            # Reset iptables
            print_info "Flushing iptables network rules..."
            sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F && sudo iptables -t raw -F
            print_success "Kubeadm cluster reset completed"
            ;;
        2)
            print_info "Resetting kubeadm cluster..."
            sudo kubeadm reset -f || true
            sudo rm -rf ~/.kube
            sudo rm -rf /etc/kubernetes/
            sudo rm -rf /var/lib/etcd/
            sudo rm -rf /var/lib/kubelet/

            # Reset iptables
            print_info "Flushing iptables network rules..."
            sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F && sudo iptables -t raw -F

            # Purging packages
            print_info "Purging Kubernetes packages, containerd, and Helm..."
            sudo apt-get purge -y kubeadm kubelet kubectl helm containerd conntrack || true
            sudo apt-get autoremove -y || true

            # Remove repo sources
            print_info "Cleaning package manager lists and keys..."
            sudo rm -f /etc/apt/sources.list.d/kubernetes.list
            sudo rm -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg
            sudo rm -f /etc/apt/sources.list.d/helm-stable-debian.list || true
            sudo rm -rf /etc/containerd/

            print_success "Kubeadm cluster and system binaries purged successfully"
            ;;
        3)
            print_info "Keeping local Kubernetes cluster intact."
            ;;
        *)
            print_error "Invalid option"
            reset_kubeadm_cluster
            ;;
    esac
}

# Main uninstallation flow
main() {
    print_header "CloudGraph Uninstallation"
    echo ""

    # Check for root/sudo if option 3 is needed
    if [ "$(id -u)" -ne 0 ] && command_exists kubeadm; then
        print_warning "This script may require sudo/root permissions if you choose to reset kubeadm."
    fi

    # Run uninstallation steps
    uninstall_helm_release
    delete_namespace
    reset_kubeadm_cluster

    print_header "Uninstallation Complete!"
    print_success "CloudGraph uninstallation finished."
    echo ""
}

# Run main function
main "$@"
