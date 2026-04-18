# ====================================================================
# GKE Cluster — Hardened Configuration
# Changes vs original:
#   - Dedicated VPC (from network.tf) instead of default VPC
#   - Workload Identity enabled (scoped: cloud-platform is now safe)
#   - Private nodes (no public IP on nodes)
#   - Release channel instead of hardcoded K8s version
#   - Shielded nodes enabled
# ====================================================================

resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.zone
  project  = var.project_id

  # Mandatory when using custom node pools
  remove_default_node_pool = true
  initial_node_count       = 1

  # Dedicated VPC (defined in network.tf)
  network    = var.network_id
  subnetwork = var.subnet_id

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods"
    services_secondary_range_name = "gke-services"
  }

  # Private nodes: no external IPs — outbound via Cloud NAT
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false   # Keep control plane accessible from your machine
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Managed release channel instead of hardcoding a version
  release_channel {
    channel = "REGULAR"
  }

  # Enable GKE Dataplane V2 (Cilium-powered)
  datapath_provider = "ADVANCED_DATAPATH"

  # Workload Identity: allows pods to use GCP IAM without SA key files
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Disable basic auth & legacy ABAC
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  # Allow terraform destroy to delete the cluster
  deletion_protection = false
}

# ====================================================================
# 1. On-Demand Node Pool (Infra) — Stateful services, always on
# ====================================================================
resource "google_container_node_pool" "infra_pool" {
  name       = "infra-pool"
  cluster    = google_container_cluster.primary.id
  location       = var.zone
  project        = var.project_id

  autoscaling {
    min_node_count = 0 
    max_node_count = 1
  }

  initial_node_count = 1

  node_config {
    machine_type = "n2-standard-8"
    disk_size_gb = 50
    disk_type    = "pd-balanced"

    spot = true


    # Node labels (for nodeSelector in pods)
    labels = {
      env  = "dev"
      role = "infra"
    }

    # Workload Identity on nodes
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ====================================================================
# 2. Spot Node Pool (Compute) — Batch/Spark workloads
# ====================================================================
resource "google_container_node_pool" "compute_pool" {
  name       = "compute-pool"
  cluster    = google_container_cluster.primary.id
  location       = var.zone
  project        = var.project_id

  autoscaling {
    min_node_count = 0
    max_node_count = 1
  }

  initial_node_count = 1

  node_config {
    machine_type = "e2-highmem-4"
    disk_size_gb = 50
    disk_type    = "pd-balanced"

    spot = true


    labels = {
      env  = "dev"
      role = "compute"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ====================================================================
# 3. Spot Node Pool (Query & Monitor) — Trino, Superset, Grafana
# ====================================================================
resource "google_container_node_pool" "query_pool" {
  name       = "query-pool"
  cluster    = google_container_cluster.primary.id
  location       = var.zone
  project        = var.project_id

  autoscaling {
    min_node_count = 0
    max_node_count = 1
  }

  initial_node_count = 1

  node_config {
    machine_type = "e2-highmem-4"
    disk_size_gb = 50
    disk_type    = "pd-balanced"

    spot = true


    labels = {
      env  = "dev"
      role = "query"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
