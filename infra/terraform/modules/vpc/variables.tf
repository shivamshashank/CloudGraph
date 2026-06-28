variable "name_prefix" {
  description = "Prefix applied to all VPC resources."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones for subnet creation."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Whether to create NAT gateways."
  type        = bool
}

variable "single_nat_gateway" {
  description = "Whether to create a single shared NAT gateway."
  type        = bool
}

variable "cluster_name" {
  description = "Name of the EKS cluster for subnet discovery tags."
  type        = string
}
