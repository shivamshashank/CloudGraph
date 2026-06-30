output "cluster_security_group_id" {
  description = "Security group ID for the EKS control plane."
  value       = aws_security_group.cluster.id
}

output "node_security_group_id" {
  description = "Security group ID for the EKS managed node groups."
  value       = aws_security_group.node.id
}
