module "network" {
  source       = "../../modules/network"
  cluster_name = var.cluster_name
  project_id   = var.project_id
  region       = var.region
}

module "nat" {
  source       = "../../modules/nat"
  cluster_name = var.cluster_name
  project_id   = var.project_id
  region       = var.region
  network_id   = module.network.network_id
}

module "gke" {
  source       = "../../modules/gke"
  cluster_name = var.cluster_name
  project_id   = var.project_id
  zone         = var.zone
  network_id   = module.network.network_id
  subnet_id    = module.network.subnet_id
}
