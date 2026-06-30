# =============================================================================
# CloudGraph — Root Terraform Outputs
# Week 2: AWS EKS Infrastructure
#
# These outputs are surfaced after `terraform apply` and are also consumed
# by downstream modules and CI/CD scripts (e.g., kubeconfig generation).
# =============================================================================

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the CloudGraph VPC."
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the CloudGraph VPC."
  value       = module.vpc.vpc_cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets (for load balancers)."
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets (for EKS nodes)."
  value       = module.vpc.private_subnet_ids
}

output "nat_gateway_ids" {
  description = "IDs of NAT Gateways provisioned."
  value       = module.vpc.nat_gateway_ids
}

# -----------------------------------------------------------------------------
# EKS Cluster
# -----------------------------------------------------------------------------

output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint URL for the EKS Kubernetes API server."
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded certificate authority data for the EKS cluster."
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL — required to create IRSA trust policies."
  value       = module.eks.cluster_oidc_issuer_url
}

output "cluster_oidc_provider_arn" {
  description = "ARN of the IAM OIDC provider for the EKS cluster."
  value       = module.iam.oidc_provider_arn
}

output "node_group_arns" {
  description = "ARNs of all EKS managed node groups."
  value       = module.eks.node_group_arns
}

# -----------------------------------------------------------------------------
# IAM / IRSA Role ARNs
# -----------------------------------------------------------------------------

output "cluster_autoscaler_role_arn" {
  description = "IAM Role ARN for the Cluster Autoscaler service account."
  value       = module.iam.cluster_autoscaler_role_arn
}

output "aws_load_balancer_controller_role_arn" {
  description = "IAM Role ARN for the AWS Load Balancer Controller service account."
  value       = module.iam.aws_load_balancer_controller_role_arn
}

output "ebs_csi_driver_role_arn" {
  description = "IAM Role ARN for the EBS CSI Driver service account."
  value       = module.iam.ebs_csi_driver_role_arn
}

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------

output "cluster_security_group_id" {
  description = "ID of the EKS cluster security group."
  value       = module.security_groups.cluster_security_group_id
}

output "node_security_group_id" {
  description = "ID of the EKS node security group."
  value       = module.security_groups.node_security_group_id
}

# -----------------------------------------------------------------------------
# Convenience — kubeconfig command
# -----------------------------------------------------------------------------

output "kubeconfig_command" {
  description = "AWS CLI command to update the local kubeconfig for this cluster."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}
