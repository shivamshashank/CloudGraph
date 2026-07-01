variable "name_prefix" {
  description = "Prefix applied to all EKS resources."
  type        = string
}

variable "cluster_name" {
  description = "The EKS cluster name."
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for EKS nodes."
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the EKS cluster."
  type        = list(string)
}

variable "cluster_sg_id" {
  description = "Security group ID for the EKS control plane."
  type        = string
}


variable "node_groups" {
  description = "Map of EKS managed node group definitions."
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
}

variable "cluster_log_types" {
  description = "List of control plane log types to enable."
  type        = list(string)
}


variable "cluster_endpoint_public_access" {
  description = "Whether the EKS API endpoint is publicly accessible."
  type        = bool
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDR blocks allowed to reach the public EKS endpoint."
  type        = list(string)
}
