# =============================================================================
# CloudGraph — Root Terraform Variables
# Week 2: AWS EKS Infrastructure
#
# All configurable inputs for the CloudGraph AWS environment are defined here.
# Override values via terraform.tfvars or environment-specific *.tfvars files.
# =============================================================================

# -----------------------------------------------------------------------------
# General / Project
# -----------------------------------------------------------------------------

variable "project" {
  description = "Short project identifier. Used as a prefix in all resource names."
  type        = string
  default     = "cloudgraph"
}

variable "environment" {
  description = "Deployment environment: dev, staging, or prod."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region to deploy CloudGraph infrastructure."
  type        = string
  default     = "eu-west-2" # London — adjust for your region
}

variable "tags" {
  description = "Additional tags merged onto every tagged resource."
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Networking — VPC
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the CloudGraph VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of AZs to span. Must have at least 2 for EKS HA."
  type        = list(string)
  default     = ["eu-west-2a", "eu-west-2b", "eu-west-2c"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ). Used for load balancers."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ). EKS nodes run here."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]
}

variable "enable_nat_gateway" {
  description = "Whether to deploy a NAT Gateway so private nodes can reach the internet."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Use a single shared NAT Gateway to reduce cost (not HA). Set false for prod."
  type        = bool
  default     = true # dev default — set false for staging/prod
}

# -----------------------------------------------------------------------------
# EKS Cluster
# -----------------------------------------------------------------------------

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane."
  type        = string
  default     = "1.30"
}

variable "cluster_endpoint_public_access" {
  description = "Whether the EKS API server endpoint is publicly reachable."
  type        = bool
  default     = true # Restrict to known CIDRs in prod
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public EKS endpoint. Defaults to open (dev only)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "cluster_log_types" {
  description = "EKS control plane log types to send to CloudWatch."
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

# -----------------------------------------------------------------------------
# EKS Managed Node Groups
# -----------------------------------------------------------------------------

variable "node_groups" {
  description = <<-EOT
    Map of EKS managed node group configurations.
    Each entry creates a separate node group with its own instance type and scaling.
  EOT
  type = map(object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
    disk_size_gb   = number
    labels         = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  default = {
    # General workloads: app services, agents, API backend
    general = {
      instance_types = ["t3.xlarge"]
      min_size       = 1
      max_size       = 4
      desired_size   = 2
      disk_size_gb   = 50
      labels         = { role = "general" }
      taints         = []
    }
    # Observability workloads: Prometheus, Loki, Tempo, Grafana
    observability = {
      instance_types = ["t3.large"]
      min_size       = 1
      max_size       = 3
      desired_size   = 2
      disk_size_gb   = 100 # Larger disk for metric/log storage
      labels         = { role = "observability" }
      taints = [{
        key    = "dedicated"
        value  = "observability"
        effect = "NO_SCHEDULE"
      }]
    }
    # Database workloads: Neo4j and Qdrant
    database = {
      instance_types = ["r6i.large"] # Memory-optimised for graph DB
      min_size       = 1
      max_size       = 2
      desired_size   = 1
      disk_size_gb   = 200 # Neo4j and Qdrant need generous disk
      labels         = { role = "database" }
      taints = [{
        key    = "dedicated"
        value  = "database"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

# -----------------------------------------------------------------------------
# IAM / IRSA
# -----------------------------------------------------------------------------

variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts (IRSA) on the cluster."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Add-ons
# -----------------------------------------------------------------------------

variable "enable_cluster_autoscaler" {
  description = "Deploy Cluster Autoscaler via IRSA."
  type        = bool
  default     = true
}

variable "enable_aws_load_balancer_controller" {
  description = "Deploy AWS Load Balancer Controller for ALB/NLB ingress."
  type        = bool
  default     = true
}

variable "enable_ebs_csi_driver" {
  description = "Enable the EBS CSI driver add-on for persistent volumes."
  type        = bool
  default     = true
}
