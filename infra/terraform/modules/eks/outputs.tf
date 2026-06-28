output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Endpoint for the EKS control plane."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "Certificate authority data for the EKS cluster."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for the EKS cluster."
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "node_group_arns" {
  description = "ARNs of the EKS managed node groups."
  value       = values(aws_eks_node_group.this)[*].arn
}
