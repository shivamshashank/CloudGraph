output "oidc_provider_arn" {
  description = "ARN of the AWS IAM OIDC provider for the EKS cluster."
  value       = var.enable_irsa ? aws_iam_openid_connect_provider.eks[0].arn : ""
}

output "cluster_autoscaler_role_arn" {
  description = "ARN of the cluster autoscaler IAM role."
  value       = var.enable_irsa && var.enable_cluster_autoscaler ? aws_iam_role.cluster_autoscaler[0].arn : ""
}

output "aws_load_balancer_controller_role_arn" {
  description = "ARN of the AWS Load Balancer Controller IAM role."
  value       = var.enable_irsa && var.enable_aws_load_balancer_controller ? aws_iam_role.aws_load_balancer_controller[0].arn : ""
}

output "ebs_csi_driver_role_arn" {
  description = "ARN of the EBS CSI driver IAM role."
  value       = var.enable_irsa && var.enable_ebs_csi_driver ? aws_iam_role.ebs_csi_driver[0].arn : ""
}
