// =============================================================================
// CloudGraph — Terraform Test Suite
// Week 2: Infrastructure Tests
//
// Uses Terratest (https://terratest.gruntwork.io/) to validate that the
// Terraform modules produce the correct AWS resources.
//
// Prerequisites:
//   - Go >= 1.21
//   - AWS credentials with sufficient permissions in the target account
//   - go mod tidy (first time)
//
// Run all tests:
//   cd tests/terraform
//   go test -v -timeout 60m ./...
//
// Run a specific test:
//   go test -v -timeout 60m -run TestVPCModule ./...
//
// WARNING: These tests create real AWS resources and incur cost.
//          They clean up on success. On failure, run `terraform destroy`.
// =============================================================================

package test

import (
	"context"
	"fmt"
	"testing"

	"github.com/aws/aws-sdk-go-v2/service/ec2"
	"github.com/aws/aws-sdk-go-v2/service/ec2/types"
	"github.com/gruntwork-io/terratest/modules/aws"
	"github.com/gruntwork-io/terratest/modules/random"
	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// defaultRegion is used for all real-AWS tests. Override via TEST_AWS_REGION env var.
const defaultRegion = "eu-west-2"

// =============================================================================
// VPC Module Tests
// =============================================================================

// TestVPCModule verifies that the VPC module creates the expected networking
// resources with the correct CIDR, subnet, and tagging configuration.
func TestVPCModule(t *testing.T) {
	t.Parallel()

	// Unique suffix prevents naming collisions when tests run in parallel
	uniqueID := random.UniqueId()
	namePrefix := fmt.Sprintf("cg-test-%s", uniqueID)

	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		// Point at the VPC module directly for isolated unit testing
		TerraformDir: "../../infra/terraform/modules/vpc",

		Vars: map[string]interface{}{
			"name_prefix":          namePrefix,
			"vpc_cidr":             "10.99.0.0/16",
			"availability_zones":   []string{"eu-west-2a", "eu-west-2b"},
			"public_subnet_cidrs":  []string{"10.99.1.0/24", "10.99.2.0/24"},
			"private_subnet_cidrs": []string{"10.99.10.0/24", "10.99.11.0/24"},
			"enable_nat_gateway":   true,
			"single_nat_gateway":   true,
			"cluster_name":         namePrefix,
		},

		// Retry transient AWS API errors (common during parallel test runs)
		RetryableTerraformErrors: map[string]string{
			"RequestExpired":           "AWS request expired — retrying",
			"OptInRequired":            "Account not opted in — check region",
			"InvalidSubnetID.NotFound": "Subnet not yet propagated — retrying",
		},
	})

	// Always destroy at the end to avoid leaving orphaned AWS resources
	defer terraform.Destroy(t, terraformOptions)

	// Init and Apply
	terraform.InitAndApply(t, terraformOptions)

	// -------------------------------------------------------------------------
	// Assert: VPC
	// -------------------------------------------------------------------------

	vpcID := terraform.Output(t, terraformOptions, "vpc_id")
	require.NotEmpty(t, vpcID, "vpc_id output should not be empty")

	vpcCIDR := terraform.Output(t, terraformOptions, "vpc_cidr_block")
	assert.Equal(t, "10.99.0.0/16", vpcCIDR, "VPC CIDR should match input")

	// Verify the VPC exists in AWS
	vpc := aws.GetVpcById(t, vpcID, defaultRegion)
	assert.NotEmpty(t, vpc.Id, "VPC ID should not be empty")

	// Verify DNS support and hostnames are enabled using AWS EC2 client
	client := aws.NewEc2Client(t, defaultRegion)

	// Check EnableDnsSupport
	attribSupport, err := client.DescribeVpcAttribute(context.Background(), &ec2.DescribeVpcAttributeInput{
		Attribute: "enableDnsSupport",
		VpcId:     &vpcID,
	})
	require.NoError(t, err)
	assert.NotNil(t, attribSupport.EnableDnsSupport)
	assert.True(t, *attribSupport.EnableDnsSupport.Value, "DNS support must be enabled for EKS")

	// Check EnableDnsHostnames
	attribHostnames, err := client.DescribeVpcAttribute(context.Background(), &ec2.DescribeVpcAttributeInput{
		Attribute: "enableDnsHostnames",
		VpcId:     &vpcID,
	})
	require.NoError(t, err)
	assert.NotNil(t, attribHostnames.EnableDnsHostnames)
	assert.True(t, *attribHostnames.EnableDnsHostnames.Value, "DNS hostnames must be enabled for EKS")

	// -------------------------------------------------------------------------
	// Assert: Subnets
	// -------------------------------------------------------------------------

	publicSubnetIDs := terraform.OutputList(t, terraformOptions, "public_subnet_ids")
	assert.Len(t, publicSubnetIDs, 2, "Should create 2 public subnets (one per AZ)")

	privateSubnetIDs := terraform.OutputList(t, terraformOptions, "private_subnet_ids")
	assert.Len(t, privateSubnetIDs, 2, "Should create 2 private subnets (one per AZ)")

	// Public subnets must have map_public_ip_on_launch = true
	for _, subnetID := range publicSubnetIDs {
		subnet := getSubnet(t, subnetID, defaultRegion)
		assert.NotNil(t, subnet.MapPublicIpOnLaunch)
		assert.True(t, *subnet.MapPublicIpOnLaunch,
			"Public subnet %s should auto-assign public IPs", subnetID)
	}

	// Private subnets must NOT auto-assign public IPs
	for _, subnetID := range privateSubnetIDs {
		subnet := getSubnet(t, subnetID, defaultRegion)
		assert.NotNil(t, subnet.MapPublicIpOnLaunch)
		assert.False(t, *subnet.MapPublicIpOnLaunch,
			"Private subnet %s should NOT auto-assign public IPs", subnetID)
	}

	// -------------------------------------------------------------------------
	// Assert: NAT Gateway
	// -------------------------------------------------------------------------

	natGatewayIDs := terraform.OutputList(t, terraformOptions, "nat_gateway_ids")
	assert.Len(t, natGatewayIDs, 1,
		"single_nat_gateway=true should create exactly one NAT Gateway")

	// -------------------------------------------------------------------------
	// Assert: Internet Gateway
	// -------------------------------------------------------------------------

	igwID := terraform.Output(t, terraformOptions, "internet_gateway_id")
	assert.NotEmpty(t, igwID, "An Internet Gateway should be created")

	// -------------------------------------------------------------------------
	// Assert: EKS-required subnet tags
	// -------------------------------------------------------------------------

	clusterTag := fmt.Sprintf("kubernetes.io/cluster/%s", namePrefix)
	for _, subnetID := range publicSubnetIDs {
		tags := aws.GetTagsForSubnet(t, subnetID, defaultRegion)
		assert.Equal(t, "shared", tags[clusterTag],
			"Public subnet %s must have EKS cluster tag", subnetID)
		assert.Equal(t, "1", tags["kubernetes.io/role/elb"],
			"Public subnet %s must have ELB role tag", subnetID)
	}

	for _, subnetID := range privateSubnetIDs {
		tags := aws.GetTagsForSubnet(t, subnetID, defaultRegion)
		assert.Equal(t, "shared", tags[clusterTag],
			"Private subnet %s must have EKS cluster tag", subnetID)
		assert.Equal(t, "1", tags["kubernetes.io/role/internal-elb"],
			"Private subnet %s must have internal-ELB role tag", subnetID)
	}
}

// =============================================================================
// Security Groups Module Tests
// =============================================================================

// TestSecurityGroupsModule validates that the security group module creates
// the cluster and node security groups with the expected rules.
func TestSecurityGroupsModule(t *testing.T) {
	t.Parallel()

	uniqueID := random.UniqueId()
	namePrefix := fmt.Sprintf("cg-test-%s", uniqueID)

	// Security groups need a VPC — set up a minimal one first
	vpcOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../infra/terraform/modules/vpc",
		Vars: map[string]interface{}{
			"name_prefix":          namePrefix,
			"vpc_cidr":             "10.98.0.0/16",
			"availability_zones":   []string{"eu-west-2a"},
			"public_subnet_cidrs":  []string{"10.98.1.0/24"},
			"private_subnet_cidrs": []string{"10.98.10.0/24"},
			"enable_nat_gateway":   false,
			"single_nat_gateway":   true,
			"cluster_name":         namePrefix,
		},
	})
	defer terraform.Destroy(t, vpcOptions)
	terraform.InitAndApply(t, vpcOptions)

	vpcID := terraform.Output(t, vpcOptions, "vpc_id")

	// Now test the security groups module
	sgOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../../infra/terraform/modules/security-groups",
		Vars: map[string]interface{}{
			"name_prefix":  namePrefix,
			"vpc_id":       vpcID,
			"vpc_cidr":     "10.98.0.0/16",
			"cluster_name": namePrefix,
		},
	})
	defer terraform.Destroy(t, sgOptions)
	terraform.InitAndApply(t, sgOptions)

	// -------------------------------------------------------------------------
	// Assert: Security Groups exist
	// -------------------------------------------------------------------------

	clusterSGID := terraform.Output(t, sgOptions, "cluster_security_group_id")
	nodeSGID := terraform.Output(t, sgOptions, "node_security_group_id")

	require.NotEmpty(t, clusterSGID, "cluster_security_group_id must not be empty")
	require.NotEmpty(t, nodeSGID, "node_security_group_id must not be empty")

	// Verify the SGs exist in the correct VPC
	clusterSG := getSecurityGroup(t, clusterSGID, defaultRegion)
	assert.Equal(t, vpcID, *clusterSG.VpcId,
		"Cluster SG should be in the correct VPC")

	nodeSG := getSecurityGroup(t, nodeSGID, defaultRegion)
	assert.Equal(t, vpcID, *nodeSG.VpcId,
		"Node SG should be in the correct VPC")

	// -------------------------------------------------------------------------
	// Assert: Names follow naming convention
	// -------------------------------------------------------------------------

	assert.Equal(t, fmt.Sprintf("%s-eks-cluster-sg", namePrefix), *clusterSG.GroupName)
	assert.Equal(t, fmt.Sprintf("%s-eks-node-sg", namePrefix), *nodeSG.GroupName)
}

// =============================================================================
// Plan-Only Tests (no real AWS resources)
// These tests validate the Terraform plan output without creating anything.
// Safe to run in CI without AWS credentials that can create resources.
// =============================================================================

// TestVPCPlanValidation runs terraform plan and checks for expected resource types.
// This is a lightweight sanity check that doesn't require real AWS access.
func TestVPCPlanValidation(t *testing.T) {
	t.Parallel()

	terraformOptions := &terraform.Options{
		TerraformDir: "../../infra/terraform/modules/vpc",
		Vars: map[string]interface{}{
			"name_prefix":          "cg-plan-test",
			"vpc_cidr":             "10.97.0.0/16",
			"availability_zones":   []string{"eu-west-2a", "eu-west-2b"},
			"public_subnet_cidrs":  []string{"10.97.1.0/24", "10.97.2.0/24"},
			"private_subnet_cidrs": []string{"10.97.10.0/24", "10.97.11.0/24"},
			"enable_nat_gateway":   true,
			"single_nat_gateway":   true,
			"cluster_name":         "cg-plan-test",
		},
		// Plan only — no AWS calls that create resources
		PlanFilePath: "/tmp/cg-vpc-plan.tfplan",
	}

	// Init and Plan (no Apply)
	terraform.Init(t, terraformOptions)
	planOutput := terraform.Plan(t, terraformOptions)

	// Validate expected resource types appear in the plan
	assert.Contains(t, planOutput, "aws_vpc.this",
		"Plan should include a VPC resource")
	assert.Contains(t, planOutput, "aws_subnet.public",
		"Plan should include public subnets")
	assert.Contains(t, planOutput, "aws_subnet.private",
		"Plan should include private subnets")
	assert.Contains(t, planOutput, "aws_internet_gateway.this",
		"Plan should include an Internet Gateway")
	assert.Contains(t, planOutput, "aws_nat_gateway.this",
		"Plan should include a NAT Gateway")
	assert.Contains(t, planOutput, "aws_route_table.public",
		"Plan should include a public route table")
	assert.Contains(t, planOutput, "aws_route_table.private",
		"Plan should include a private route table")
	assert.Contains(t, planOutput, "aws_flow_log.this",
		"Plan should include VPC flow logs for security auditing")
}

// TestVariableValidation verifies that invalid variable values are rejected.
func TestVariableValidation(t *testing.T) {
	t.Parallel()

	// Intentionally invalid CIDR — should fail validation
	terraformOptions := &terraform.Options{
		TerraformDir: "../../infra/terraform",
		Vars: map[string]interface{}{
			"environment": "invalid-env", // Only dev/staging/prod allowed
		},
	}

	terraform.Init(t, terraformOptions)

	// Expect a plan failure due to variable validation
	_, err := terraform.PlanE(t, terraformOptions)
	require.Error(t, err, "Terraform plan should fail for invalid environment")
	assert.Contains(t, err.Error(), "environment must be one of",
		"Error message should reference the validation rule")
}

// =============================================================================
// Helper — retry with timeout (used for eventually-consistent AWS checks)
// =============================================================================

func getSubnet(t *testing.T, subnetID string, region string) types.Subnet {
	client := aws.NewEc2Client(t, region)
	resp, err := client.DescribeSubnets(context.Background(), &ec2.DescribeSubnetsInput{
		SubnetIds: []string{subnetID},
	})
	require.NoError(t, err)
	require.Len(t, resp.Subnets, 1)
	return resp.Subnets[0]
}

func getSecurityGroup(t *testing.T, sgID string, region string) types.SecurityGroup {
	client := aws.NewEc2Client(t, region)
	resp, err := client.DescribeSecurityGroups(context.Background(), &ec2.DescribeSecurityGroupsInput{
		GroupIds: []string{sgID},
	})
	require.NoError(t, err)
	require.Len(t, resp.SecurityGroups, 1)
	return resp.SecurityGroups[0]
}
