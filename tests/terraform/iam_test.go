package test

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

// TestIAMPlanValidation validates the IAM module plan output without creating AWS resources.
func TestIAMPlanValidation(t *testing.T) {
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../../infra/terraform/modules/iam",
		Vars: map[string]interface{}{
			"name_prefix":                         "cg-iam-plan-test",
			"cluster_name":                        "cg-iam-plan-test",
			"cluster_oidc_issuer_url":             "https://oidc.eks.eu-west-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B716D3041E",
			"enable_irsa":                         true,
			"enable_cluster_autoscaler":           true,
			"enable_aws_load_balancer_controller": true,
			"enable_ebs_csi_driver":               true,
		},
		PlanFilePath: "/tmp/cg-iam-plan.tfplan",
	}

	terraform.Init(t, terraformOptions)
	planOutput := terraform.Plan(t, terraformOptions)

	// Validate expected resources appear in the plan
	assert.Contains(t, planOutput, "aws_iam_openid_connect_provider.eks",
		"Plan should include EKS OIDC provider")
	assert.Contains(t, planOutput, "aws_iam_role.cluster_autoscaler",
		"Plan should include Cluster Autoscaler IAM role")
	assert.Contains(t, planOutput, "aws_iam_role.aws_load_balancer_controller",
		"Plan should include AWS Load Balancer Controller IAM role")
	assert.Contains(t, planOutput, "aws_iam_role.ebs_csi_driver",
		"Plan should include EBS CSI Driver IAM role")
}
