output "cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  description = "GKE cluster API endpoint"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate (base64 encoded)"
  value       = google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "connect_command" {
  description = "gcloud command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.primary.name} --zone ${var.zone} --project ${var.project_id}"
}

output "vpc_name" {
  description = "Name of the dedicated VPC"
  value       = google_compute_network.vpc.name
}

output "subnet_name" {
  description = "Name of the GKE subnet"
  value       = google_compute_subnetwork.subnet.name
}
