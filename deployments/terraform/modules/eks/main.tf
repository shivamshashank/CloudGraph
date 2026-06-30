# =============================================================================
# CloudGraph — EKS Module
# Week 2: Kubernetes Control Plane + Managed Node Groups
#
# Creates:
#   - IAM role for the EKS control plane
#   - EKS cluster (control plane)
#   - CloudWatch log group for control plane logs
#   - IAM role for managed node groups
#   - EKS managed node groups (general, observability, database)
#   - EKS managed add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI Driver)
# =============================================================================

# -----------------------------------------------------------------------------
# CloudWatch Log Group for EKS Control Plane Logs
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = 30

  tags = {
    Name = "${var.name_prefix}-eks-logs"
  }
}

# -----------------------------------------------------------------------------
# IAM Role — EKS Control Plane
# The EKS service assumes this role to manage AWS resources on behalf of
# the cluster (e.g., creating ENIs, managing load balancers).
# -----------------------------------------------------------------------------

resource "aws_iam_role" "cluster" {
  name = "${var.name_prefix}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${var.name_prefix}-eks-cluster-role"
  }
}

# Attach the AWS-managed EKS cluster policy
resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSClusterPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

# Attach VPC resource controller policy (for security group assignment)
resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSVPCResourceController" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.name
}

# -----------------------------------------------------------------------------
# EKS Cluster (Control Plane)
# -----------------------------------------------------------------------------

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = concat(var.private_subnet_ids, var.public_subnet_ids)
    security_group_ids      = [var.cluster_sg_id]
    endpoint_private_access = true # Nodes communicate with API privately
    endpoint_public_access  = var.cluster_endpoint_public_access
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  # Enable control plane logging to CloudWatch
  enabled_cluster_log_types = var.cluster_log_types

  # Encrypt Kubernetes secrets at rest using an AWS-managed KMS key
  # (for production, use a customer-managed KMS key)
  # encryption_config {
  #   provider {
  #     key_arn = aws_kms_key.eks.arn
  #   }
  #   resources = ["secrets"]
  # }

  tags = {
    Name = var.cluster_name
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster_AmazonEKSClusterPolicy,
    aws_iam_role_policy_attachment.cluster_AmazonEKSVPCResourceController,
    aws_cloudwatch_log_group.eks,
  ]
}

# -----------------------------------------------------------------------------
# IAM Role — EKS Node Groups
# EC2 instances in node groups assume this role to call AWS APIs
# (ECR image pulls, CloudWatch metrics, EBS management, etc.).
# -----------------------------------------------------------------------------

resource "aws_iam_role" "node_group" {
  name = "${var.name_prefix}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${var.name_prefix}-eks-node-role"
  }
}

# Allows nodes to register with EKS and pull cluster info
resource "aws_iam_role_policy_attachment" "node_AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node_group.name
}

# Allows nodes to pull container images from ECR
resource "aws_iam_role_policy_attachment" "node_AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node_group.name
}

# Required for the VPC CNI plugin (manages pod networking / ENIs)
resource "aws_iam_role_policy_attachment" "node_AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node_group.name
}

# Allows CloudWatch Container Insights to collect node metrics
resource "aws_iam_role_policy_attachment" "node_CloudWatchAgentServerPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  role       = aws_iam_role.node_group.name
}

# SSM access so you can shell into nodes via Session Manager (no SSH bastion needed)
resource "aws_iam_role_policy_attachment" "node_AmazonSSMManagedInstanceCore" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.node_group.name
}

# -----------------------------------------------------------------------------
# EKS Managed Node Groups
# Defined dynamically from var.node_groups — see variables.tf for structure.
# -----------------------------------------------------------------------------

resource "aws_eks_node_group" "this" {
  for_each = var.node_groups

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name_prefix}-ng-${each.key}"
  node_role_arn   = aws_iam_role.node_group.arn

  # Place nodes in private subnets for security
  subnet_ids = var.private_subnet_ids

  # Instance configuration
  instance_types = each.value.instance_types
  disk_size      = each.value.disk_size_gb

  # Auto Scaling Group sizing
  scaling_config {
    min_size     = each.value.min_size
    max_size     = each.value.max_size
    desired_size = each.value.desired_size
  }

  # Rolling update strategy — replaces nodes gracefully
  update_config {
    max_unavailable_percentage = 25
  }

  # Kubernetes labels applied to every node in this group
  labels = each.value.labels

  # Kubernetes taints — used to dedicate nodes to specific workloads
  dynamic "taint" {
    for_each = each.value.taints
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  tags = {
    Name                                            = "${var.name_prefix}-ng-${each.key}"
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.node_AmazonEC2ContainerRegistryReadOnly,
    aws_iam_role_policy_attachment.node_AmazonEKS_CNI_Policy,
  ]

  # Prevent Terraform from destroying nodes when only desired_size changes —
  # Cluster Autoscaler manages that at runtime.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# -----------------------------------------------------------------------------
# EKS Managed Add-ons
# These are AWS-managed Kubernetes system components.
# -----------------------------------------------------------------------------

# CoreDNS — in-cluster DNS resolution
resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = {
    Name = "${var.name_prefix}-addon-coredns"
  }

  depends_on = [aws_eks_node_group.this]
}

# kube-proxy — manages iptables / eBPF rules for Services
resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "kube-proxy"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = {
    Name = "${var.name_prefix}-addon-kube-proxy"
  }
}

# Amazon VPC CNI — assigns VPC IPs to pods
resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "vpc-cni"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = {
    Name = "${var.name_prefix}-addon-vpc-cni"
  }
}
