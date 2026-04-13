# ====================================================================
# Google Provider Configuration
# The terraform{} block (required_version, required_providers, backend)
# is defined in backend.tf — do NOT duplicate it here.
# ====================================================================

provider "google" {
  project = var.project_id
  region  = var.region
}
