variable "name_prefix" {
  description = "Prefix applied to all security group resources."
  type        = string
}

variable "vpc_id" {
  description = "The VPC ID where the security groups will be created."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}
