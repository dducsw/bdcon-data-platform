variable "project_id" {
  description = "The GCP project ID to deploy resources in. Required — set in terraform.tfvars."
  type        = string
  # No default: forces explicit input, preventing accidental deployment to wrong project.
}

variable "region" {
  description = "GCP region for the cluster and network resources"
  type        = string
  default     = "asia-east2" # Hong Kong
}

variable "zone" {
  description = "GCP zone for the zonal GKE cluster"
  type        = string
  default     = "asia-east2-a"
}

variable "cluster_name" {
  description = "Name of the GKE cluster (also used as prefix for VPC/subnet)"
  type        = string
  default     = "data-platform-cluster"
}
