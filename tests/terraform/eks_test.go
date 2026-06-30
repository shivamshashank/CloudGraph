package test

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

// TestEKSPlanValidation validates the EKS module plan output without creating AWS resources.
func TestEKSPlanValidation(t *testing.T) {
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../../deployments/terraform/modules/eks",
		Vars: map[string]interface{}{
			"name_prefix":     "cg-eks-plan-test",
			"cluster_name":    "cg-eks-plan-test",
			"cluster_version": "1.28",
			"private_subnet_ids": []string{
				"subnet-0123456789abcdef0",
				"subnet-0123456789abcdef1",
			},
			"public_subnet_ids": []string{
				"subnet-0123456789abcdef2",
				"subnet-0123456789abcdef3",
			},
			"cluster_sg_id": "sg-0123456789abcdef0",
			"node_sg_id":    "sg-0123456789abcdef1",
			"node_groups": map[string]interface{}{
				"general": map[string]interface{}{
					"instance_types": []string{"t3.medium"},
					"min_size":       1,
					"max_size":       3,
					"desired_size":   2,
					"disk_size_gb":   20,
					"labels":         map[string]string{"role": "general"},
					"taints":         []interface{}{},
				},
			},
			"cluster_log_types":                    []string{"api", "audit"},
			"enable_ebs_csi_driver":                true,
			"cluster_endpoint_public_access":       true,
			"cluster_endpoint_public_access_cidrs": []string{"0.0.0.0/0"},
		},
		PlanFilePath: "/tmp/cg-eks-plan.tfplan",
	}

	writeDummyProvider(t, terraformOptions.TerraformDir)

	terraform.Init(t, terraformOptions)
	planOutput := terraform.Plan(t, terraformOptions)

	// Validate expected resources appear in the plan
	assert.Contains(t, planOutput, "aws_eks_cluster.this",
		"Plan should include the EKS cluster control plane")
	assert.Contains(t, planOutput, "aws_iam_role.cluster",
		"Plan should include EKS control plane IAM role")
	assert.Contains(t, planOutput, "aws_iam_role.node_group",
		"Plan should include worker node group IAM role")
	assert.Contains(t, planOutput, "aws_eks_node_group.this",
		"Plan should include worker node groups")
	assert.Contains(t, planOutput, "aws_eks_addon.coredns",
		"Plan should include coredns addon")
}
