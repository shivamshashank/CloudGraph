# =============================================================================
# CloudGraph — Security Groups Module
# Week 2: Least-Privilege Firewall Rules
#
# Creates two security groups:
#   1. cluster_sg — attached to the EKS control plane
#   2. node_sg    — attached to all EKS managed node group instances
#
# Rules follow AWS EKS documentation for required inter-node and node-to-API
# communication, plus CloudGraph-specific ports for observability tools.
# =============================================================================

# -----------------------------------------------------------------------------
# Cluster Security Group
# Controls traffic to/from the EKS API server.
# -----------------------------------------------------------------------------

resource "aws_security_group" "cluster" {
  name        = "${var.name_prefix}-eks-cluster-sg"
  description = "Security group for the EKS control plane / API server."
  vpc_id      = var.vpc_id

  tags = {
    Name                                        = "${var.name_prefix}-eks-cluster-sg"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}

# Allow nodes to communicate with the cluster API (HTTPS 443)
resource "aws_security_group_rule" "cluster_ingress_from_nodes" {
  type                     = "ingress"
  description              = "Allow node groups to reach the EKS API server."
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.node.id
  security_group_id        = aws_security_group.cluster.id
}

# Egress: allow all outbound (control plane needs to reach AWS services)
resource "aws_security_group_rule" "cluster_egress_all" {
  type              = "egress"
  description       = "Allow all outbound traffic from the control plane."
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.cluster.id
}

# -----------------------------------------------------------------------------
# Node Security Group
# Attached to EC2 instances in all managed node groups.
# -----------------------------------------------------------------------------

resource "aws_security_group" "node" {
  name        = "${var.name_prefix}-eks-node-sg"
  description = "Security group for EKS managed node group instances."
  vpc_id      = var.vpc_id

  tags = {
    Name                                        = "${var.name_prefix}-eks-node-sg"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}

# Nodes must be able to talk to each other (pod-to-pod, kubelet, etc.)
resource "aws_security_group_rule" "node_ingress_self" {
  type                     = "ingress"
  description              = "Allow all traffic between nodes in the same node security group."
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.node.id
  security_group_id        = aws_security_group.node.id
}

# Control plane sends webhooks and kubelet calls to nodes on 10250
resource "aws_security_group_rule" "node_ingress_from_cluster_kubelet" {
  type                     = "ingress"
  description              = "Allow EKS control plane to reach kubelet on nodes."
  from_port                = 10250
  to_port                  = 10250
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.cluster.id
  security_group_id        = aws_security_group.node.id
}

# EKS-managed add-ons and admission webhooks use ephemeral ports
resource "aws_security_group_rule" "node_ingress_from_cluster_ephemeral" {
  type                     = "ingress"
  description              = "Allow EKS control plane to reach admission webhook ports."
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.cluster.id
  security_group_id        = aws_security_group.node.id
}

# ALB / NLB health checks originate from within the VPC CIDR
resource "aws_security_group_rule" "node_ingress_alb_health_checks" {
  type              = "ingress"
  description       = "Allow ALB/NLB health check traffic from within the VPC."
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Prometheus scraping — port 9090 within VPC (inter-node metrics collection)
resource "aws_security_group_rule" "node_ingress_prometheus" {
  type              = "ingress"
  description       = "Allow Prometheus scraping on port 9090 from within the VPC."
  from_port         = 9090
  to_port           = 9090
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Grafana dashboard — port 3000 within VPC
resource "aws_security_group_rule" "node_ingress_grafana" {
  type              = "ingress"
  description       = "Allow Grafana dashboard access on port 3000 from within the VPC."
  from_port         = 3000
  to_port           = 3000
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Neo4j Bolt protocol — port 7687 within VPC (graph DB queries)
resource "aws_security_group_rule" "node_ingress_neo4j_bolt" {
  type              = "ingress"
  description       = "Allow Neo4j Bolt protocol access on port 7687 from within the VPC."
  from_port         = 7687
  to_port           = 7687
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Neo4j HTTP browser — port 7474 within VPC (admin UI only, not exposed externally)
resource "aws_security_group_rule" "node_ingress_neo4j_http" {
  type              = "ingress"
  description       = "Allow Neo4j browser UI on port 7474 from within the VPC."
  from_port         = 7474
  to_port           = 7474
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Qdrant REST API — port 6333 within VPC (vector DB)
resource "aws_security_group_rule" "node_ingress_qdrant_rest" {
  type              = "ingress"
  description       = "Allow Qdrant REST API access on port 6333 from within the VPC."
  from_port         = 6333
  to_port           = 6333
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Qdrant gRPC — port 6334 within VPC
resource "aws_security_group_rule" "node_ingress_qdrant_grpc" {
  type              = "ingress"
  description       = "Allow Qdrant gRPC access on port 6334 from within the VPC."
  from_port         = 6334
  to_port           = 6334
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.node.id
}

# Egress: allow all outbound from nodes (ECR pulls, AWS API calls, internet)
resource "aws_security_group_rule" "node_egress_all" {
  type              = "egress"
  description       = "Allow all outbound traffic from nodes."
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.node.id
}
