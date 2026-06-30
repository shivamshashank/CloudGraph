# =============================================================================
# CloudGraph — IAM Module
# Week 2: OIDC Provider + IRSA Roles
#
# IRSA (IAM Roles for Service Accounts) lets Kubernetes service accounts
# assume AWS IAM roles without storing credentials in Pods. Each add-on
# gets its own scoped IAM role with a least-privilege policy.
#
# Creates:
#   - TLS certificate fingerprint for the OIDC issuer
#   - AWS IAM OIDC Identity Provider for the EKS cluster
#   - IRSA role for Cluster Autoscaler
#   - IRSA role for AWS Load Balancer Controller
#   - IRSA role for EBS CSI Driver
# =============================================================================

# -----------------------------------------------------------------------------
# OIDC Provider
# Allows EKS service accounts to authenticate as IAM principals.
# The TLS thumbprint must match the OIDC issuer's certificate.
# -----------------------------------------------------------------------------

data "tls_certificate" "eks_oidc" {
  url = var.cluster_oidc_issuer_url
}

resource "aws_iam_openid_connect_provider" "eks" {
  count = var.enable_irsa ? 1 : 0

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_oidc.certificates[0].sha1_fingerprint]
  url             = var.cluster_oidc_issuer_url

  tags = {
    Name = "${var.name_prefix}-eks-oidc-provider"
  }
}

# -----------------------------------------------------------------------------
# Local helpers — extract OIDC provider host (used in trust policy conditions)
# -----------------------------------------------------------------------------

locals {
  oidc_provider_arn = var.enable_irsa ? aws_iam_openid_connect_provider.eks[0].arn : ""
  # Strip "https://" prefix for use in IAM StringEquals condition keys
  oidc_provider_id = replace(var.cluster_oidc_issuer_url, "https://", "")
}

# =============================================================================
# IRSA Role 1 — Cluster Autoscaler
# Allows the Cluster Autoscaler pod to describe and modify ASGs so it can
# scale node groups in and out based on pending pods.
# =============================================================================

resource "aws_iam_role" "cluster_autoscaler" {
  count = (var.enable_irsa && var.enable_cluster_autoscaler) ? 1 : 0

  name = "${var.name_prefix}-cluster-autoscaler-role"

  # Trust policy: only the cluster-autoscaler service account can assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = local.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:kube-system:cluster-autoscaler"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-cluster-autoscaler-role"
  }
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  count = (var.enable_irsa && var.enable_cluster_autoscaler) ? 1 : 0

  name = "${var.name_prefix}-cluster-autoscaler-policy"
  role = aws_iam_role.cluster_autoscaler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Describe — read-only, no resource restriction needed
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeScalingActivities",
          "autoscaling:DescribeTags",
          "ec2:DescribeLaunchTemplateVersions",
          "ec2:DescribeInstanceTypes",
          "eks:DescribeNodegroup",
        ]
        Resource = "*"
      },
      {
        # Modify — restricted to ASGs tagged as owned by this cluster
        Effect = "Allow"
        Action = [
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup",
          "autoscaling:UpdateAutoScalingGroup",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/enabled" : "true"
            "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${var.cluster_name}" : "owned"
          }
        }
      }
    ]
  })
}

# =============================================================================
# IRSA Role 2 — AWS Load Balancer Controller
# Allows the controller to create and manage ALBs and NLBs for Ingress/Service
# resources in Kubernetes.
# =============================================================================

resource "aws_iam_role" "aws_load_balancer_controller" {
  count = (var.enable_irsa && var.enable_aws_load_balancer_controller) ? 1 : 0

  name = "${var.name_prefix}-alb-controller-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = local.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-alb-controller-role"
  }
}

# AWS publishes a recommended policy for the LBC — inline version below
resource "aws_iam_role_policy" "aws_load_balancer_controller" {
  count = (var.enable_irsa && var.enable_aws_load_balancer_controller) ? 1 : 0

  name = "${var.name_prefix}-alb-controller-policy"
  role = aws_iam_role.aws_load_balancer_controller[0].id

  # Condensed version — for production use the full official policy from:
  # https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateServiceLinkedRole",
          "ec2:DescribeAccountAttributes",
          "ec2:DescribeAddresses",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeVpcs",
          "ec2:DescribeVpcPeeringConnections",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeInstances",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeTags",
          "ec2:GetCoipPoolUsage",
          "ec2:DescribeCoipPools",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:DescribeListenerCertificates",
          "elasticloadbalancing:DescribeSSLPolicies",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:DescribeTargetHealth",
          "elasticloadbalancing:DescribeTags",
          "cognito-idp:DescribeUserPoolClient",
          "acm:ListCertificates",
          "acm:DescribeCertificate",
          "iam:ListServerCertificates",
          "iam:GetServerCertificate",
          "waf-regional:GetWebACL",
          "waf-regional:GetWebACLForResource",
          "waf-regional:AssociateWebACL",
          "waf-regional:DisassociateWebACL",
          "wafv2:GetWebACL",
          "wafv2:GetWebACLForResource",
          "wafv2:AssociateWebACL",
          "wafv2:DisassociateWebACL",
          "shield:GetSubscriptionState",
          "shield:DescribeProtection",
          "shield:CreateProtection",
          "shield:DeleteProtection",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:CreateSecurityGroup",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:DeleteRule",
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:RemoveTags",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:SetIpAddressType",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:DeregisterTargets",
          "elasticloadbalancing:SetWebAcl",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:AddListenerCertificates",
          "elasticloadbalancing:RemoveListenerCertificates",
          "elasticloadbalancing:ModifyRule",
        ]
        Resource = "*"
      }
    ]
  })
}

# =============================================================================
# IRSA Role 3 — EBS CSI Driver
# Allows the CSI driver to manage EBS volumes for PersistentVolumes.
# =============================================================================

resource "aws_iam_role" "ebs_csi_driver" {
  count = (var.enable_irsa && var.enable_ebs_csi_driver) ? 1 : 0

  name = "${var.name_prefix}-ebs-csi-driver-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = local.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider_id}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
          "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-ebs-csi-driver-role"
  }
}

resource "aws_iam_role_policy_attachment" "ebs_csi_driver" {
  count = (var.enable_irsa && var.enable_ebs_csi_driver) ? 1 : 0

  # AWS-managed policy covers all EBS CSI operations
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  role       = aws_iam_role.ebs_csi_driver[0].name
}
