# =============================================================================
# CloudGraph — VPC Module
# Week 2: Networking
#
# Creates:
#   - VPC
#   - Public subnets (one per AZ)  — for ALB/NLB load balancers
#   - Private subnets (one per AZ) — for EKS nodes (no direct internet)
#   - Internet Gateway
#   - NAT Gateway(s)
#   - Route tables
#
# EKS-required subnet tags are applied automatically so the Kubernetes
# cloud controller and AWS Load Balancer Controller can discover subnets.
# =============================================================================

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

resource "aws_vpc" "this" {
  cidr_block = var.vpc_cidr

  # Required for EKS: enables private DNS resolution within the VPC
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

# -----------------------------------------------------------------------------
# Internet Gateway — allows public subnets to reach the internet
# -----------------------------------------------------------------------------

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

# -----------------------------------------------------------------------------
# Public Subnets
# One per Availability Zone — used by load balancers.
# -----------------------------------------------------------------------------

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true # Instances in public subnet get a public IP

  tags = {
    Name = "${var.name_prefix}-public-${var.availability_zones[count.index]}"

    # EKS tag: tells AWS Load Balancer Controller this subnet is for internet-facing ELBs
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }
}

# -----------------------------------------------------------------------------
# Private Subnets
# One per Availability Zone — EKS managed node groups run here.
# -----------------------------------------------------------------------------

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.name_prefix}-private-${var.availability_zones[count.index]}"

    # EKS tag: tells AWS Load Balancer Controller this subnet is for internal ELBs
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }
}

# -----------------------------------------------------------------------------
# Elastic IPs for NAT Gateways
# -----------------------------------------------------------------------------

resource "aws_eip" "nat" {
  # Create one EIP per NAT Gateway needed
  count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.availability_zones)) : 0

  domain = "vpc"

  tags = {
    Name = "${var.name_prefix}-nat-eip-${count.index}"
  }

  depends_on = [aws_internet_gateway.this]
}

# -----------------------------------------------------------------------------
# NAT Gateway(s)
# Placed in public subnets so private nodes can reach the internet (e.g., ECR).
# single_nat_gateway = true  → one shared NAT (cheaper, no HA)
# single_nat_gateway = false → one NAT per AZ (HA, recommended for prod)
# -----------------------------------------------------------------------------

resource "aws_nat_gateway" "this" {
  count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.availability_zones)) : 0

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id # NAT GW lives in a public subnet

  tags = {
    Name = "${var.name_prefix}-nat-${count.index}"
  }

  depends_on = [aws_internet_gateway.this]
}

# -----------------------------------------------------------------------------
# Route Tables — Public
# Routes 0.0.0.0/0 through the Internet Gateway.
# -----------------------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.name_prefix}-rt-public"
  }
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# -----------------------------------------------------------------------------
# Route Tables — Private
# Routes 0.0.0.0/0 through the NAT Gateway.
# With a single NAT, all private subnets share one route table.
# With per-AZ NATs, each private subnet gets its own route table.
# -----------------------------------------------------------------------------

resource "aws_route_table" "private" {
  # One route table per private subnet when using per-AZ NATs, else one shared
  count = var.enable_nat_gateway ? (var.single_nat_gateway ? 1 : length(var.availability_zones)) : 1

  vpc_id = aws_vpc.this.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = var.single_nat_gateway ? aws_nat_gateway.this[0].id : aws_nat_gateway.this[count.index].id
    }
  }

  tags = {
    Name = "${var.name_prefix}-rt-private-${count.index}"
  }
}

resource "aws_route_table_association" "private" {
  count = length(aws_subnet.private)

  subnet_id = aws_subnet.private[count.index].id
  # Map each private subnet to its route table (or the single shared one)
  route_table_id = var.single_nat_gateway ? aws_route_table.private[0].id : aws_route_table.private[count.index].id
}

# -----------------------------------------------------------------------------
# VPC Flow Logs — sends network traffic metadata to CloudWatch for auditing
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/${var.name_prefix}/flow-logs"
  retention_in_days = 30 # Adjust based on compliance requirements

  tags = {
    Name = "${var.name_prefix}-vpc-flow-logs"
  }
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "${var.name_prefix}-vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "${var.name_prefix}-vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_flow_log" "this" {
  vpc_id          = aws_vpc.this.id
  traffic_type    = "ALL"
  iam_role_arn    = aws_iam_role.vpc_flow_logs.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_logs.arn

  tags = {
    Name = "${var.name_prefix}-flow-log"
  }
}
