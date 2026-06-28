# =============================================================================
# CloudGraph — Root Terraform Configuration
# Week 2: AWS EKS Infrastructure
#
# This is the root module. It wires together four child modules:
#   1. VPC          — networking, subnets, NAT, route tables
#   2. Security Groups — cluster and node group firewall rules
#   3. EKS          — control plane, managed node groups, add-ons
#   4. IAM          — OIDC provider + IRSA roles for add-ons
#
# Usage:
#   terraform init
#   terraform plan -var-file=../../environments/dev/terraform.tfvars
#   terraform apply -var-file=../../environments/dev/terraform.tfvars
# =============================================================================

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # ---------------------------------------------------------------------------
  # Remote state — swap the bucket/key for your environment.
  # Comment out this block when running locally without an S3 backend.
  # ---------------------------------------------------------------------------
  # backend "s3" {
  #   bucket         = "cloudgraph-terraform-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "eu-west-2"
  #   dynamodb_table = "cloudgraph-terraform-locks"
  #   encrypt        = true
  # }
}

# -----------------------------------------------------------------------------
# Provider configuration
# -----------------------------------------------------------------------------

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = var.project
        Environment = var.environment
        ManagedBy   = "Terraform"
        Repository  = "cloudgraph"
      },
      var.tags
    )
  }
}

# -----------------------------------------------------------------------------
# Local computed values shared across modules
# -----------------------------------------------------------------------------

locals {
  # Consistent name prefix for all resources
  name_prefix = "${var.project}-${var.environment}"

  # Cluster name derived from prefix (also used as EKS cluster name tag key)
  cluster_name = local.name_prefix
}

# -----------------------------------------------------------------------------
# Module 1 — VPC
# Provisions the network: VPC, public/private subnets, IGW, NAT, route tables.
# -----------------------------------------------------------------------------

module "vpc" {
  source = "./modules/vpc"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  cluster_name         = local.cluster_name # Required for EKS subnet discovery tags
}

# -----------------------------------------------------------------------------
# Module 2 — Security Groups
# Defines the cluster SG and the node SG with least-privilege ingress/egress.
# -----------------------------------------------------------------------------

module "security_groups" {
  source = "./modules/security-groups"

  name_prefix  = local.name_prefix
  vpc_id       = module.vpc.vpc_id
  vpc_cidr     = var.vpc_cidr
  cluster_name = local.cluster_name
}

# -----------------------------------------------------------------------------
# Module 3 — EKS
# Provisions the EKS control plane and managed node groups.
# -----------------------------------------------------------------------------

module "eks" {
  source = "./modules/eks"

  name_prefix           = local.name_prefix
  cluster_name          = local.cluster_name
  cluster_version       = var.cluster_version
  private_subnet_ids    = module.vpc.private_subnet_ids
  public_subnet_ids     = module.vpc.public_subnet_ids
  cluster_sg_id         = module.security_groups.cluster_security_group_id
  node_sg_id            = module.security_groups.node_security_group_id
  node_groups           = var.node_groups
  cluster_log_types     = var.cluster_log_types
  enable_ebs_csi_driver = var.enable_ebs_csi_driver

  cluster_endpoint_public_access       = var.cluster_endpoint_public_access
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
}

# -----------------------------------------------------------------------------
# Module 4 — IAM / IRSA
# Creates the OIDC provider and per-add-on IAM roles with trust policies.
# -----------------------------------------------------------------------------

module "iam" {
  source = "./modules/iam"

  name_prefix                         = local.name_prefix
  cluster_name                        = local.cluster_name
  cluster_oidc_issuer_url             = module.eks.cluster_oidc_issuer_url
  enable_irsa                         = var.enable_irsa
  enable_cluster_autoscaler           = var.enable_cluster_autoscaler
  enable_aws_load_balancer_controller = var.enable_aws_load_balancer_controller
  enable_ebs_csi_driver               = var.enable_ebs_csi_driver
}
