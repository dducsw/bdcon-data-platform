# ====================================================================
# Terraform Backend & Provider Requirements
# ====================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Remote state stored in GCS — prevents state loss and enables team collaboration.
  # Create the bucket first: gsutil mb -p PROJECT_ID gs://YOUR_TFSTATE_BUCKET
  backend "gcs" {
    bucket = "k8s-data-platform-1879-tfstate" 
    prefix = "k8s-data-platform/state"
  }
}
