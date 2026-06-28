# =============================================================================
# CloudGraph — Dev Environment Configuration
# Week 2: AWS EKS Infrastructure
#
# Usage:
#   terraform plan  -var-file=environments/dev/terraform.tfvars
#   terraform apply -var-file=environments/dev/terraform.tfvars
#
# This file contains non-secret values. Never commit secrets here.
# Store sensitive values (API keys, tokens) in AWS Secrets Manager or
# inject them as environment variables: TF_VAR_<name>=<value>
# =============================================================================

project     = "cloudgraph"
environment = "dev"
aws_region  = "eu-west-2"

# -----------------------------------------------------------------------------
# VPC — dev uses a single NAT gateway to minimise cost
# -----------------------------------------------------------------------------

vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["eu-west-2a", "eu-west-2b"]
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
enable_nat_gateway   = true
single_nat_gateway   = true # Cost saving for dev; set false in prod for HA

# -----------------------------------------------------------------------------
# EKS Cluster
# -----------------------------------------------------------------------------

cluster_version = "1.30"

# In dev, allow your office/home IP — replace with your actual CIDRs in prod
cluster_endpoint_public_access       = true
cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"] # Restrict in staging/prod!

cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

# -----------------------------------------------------------------------------
# Node Groups — smaller instances for dev cost control
# 3 groups: general workloads, observability stack, database tier
# -----------------------------------------------------------------------------

node_groups = {
  general = {
    instance_types = ["t3.large"] # 2 vCPU, 8 GB — app services and agents
    min_size       = 1
    max_size       = 3
    desired_size   = 2
    disk_size_gb   = 50
    labels         = { role = "general", env = "dev" }
    taints         = []
  }

  observability = {
    instance_types = ["t3.large"] # Prometheus, Grafana, Loki, Tempo
    min_size       = 1
    max_size       = 2
    desired_size   = 1
    disk_size_gb   = 80
    labels         = { role = "observability", env = "dev" }
    taints = [{
      key    = "dedicated"
      value  = "observability"
      effect = "NO_SCHEDULE"
    }]
  }

  database = {
    instance_types = ["r6i.large"] # 2 vCPU, 16 GB RAM — memory-optimised for Neo4j + Qdrant
    min_size       = 1
    max_size       = 2
    desired_size   = 1
    disk_size_gb   = 150
    labels         = { role = "database", env = "dev" }
    taints = [{
      key    = "dedicated"
      value  = "database"
      effect = "NO_SCHEDULE"
    }]
  }
}

# -----------------------------------------------------------------------------
# Add-ons / IAM
# -----------------------------------------------------------------------------

enable_irsa                         = true
enable_cluster_autoscaler           = true
enable_aws_load_balancer_controller = true
enable_ebs_csi_driver               = true

# -----------------------------------------------------------------------------
# Extra tags applied to all resources
# -----------------------------------------------------------------------------

tags = {
  Owner   = "cloudgraph-team"
  Purpose = "dissertation-prototype"
  Week    = "2"
}
