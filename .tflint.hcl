# =============================================================================
# CloudGraph — TFLint Configuration
# =============================================================================

config {
  call_module_type = "all"
  force = false
}

# Disable rule requiring explicit Terraform version constraints
rule "terraform_required_version" {
  enabled = false
}

# Disable rule requiring explicit provider version constraints inside modules
rule "terraform_required_providers" {
  enabled = false
}

# Disable rule checking for unused declarations (variables/data sources)
# to prevent local test configs from failing lint checks
rule "terraform_unused_declarations" {
  enabled = false
}
