variable "name_prefix" {
  description = "Prefix applied to all IAM resources."
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for the EKS cluster."
  type        = string
}

variable "enable_irsa" {
  description = "Whether to create OIDC provider and IRSA roles."
  type        = bool
}

variable "enable_cluster_autoscaler" {
  description = "Whether to create the cluster autoscaler IRSA role."
  type        = bool
}

variable "enable_aws_load_balancer_controller" {
  description = "Whether to create the AWS Load Balancer Controller IRSA role."
  type        = bool
}

variable "enable_ebs_csi_driver" {
  description = "Whether to create the EBS CSI driver IRSA role."
  type        = bool
}
