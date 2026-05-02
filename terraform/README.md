# Terraform Layout

- `modules/`: Reusable infrastructure building blocks
- `envs/dev`: Active development environment entrypoint
- `envs/lab`: Optional parallel lab environment

---

## 🚀 How to Provision the Cluster

Infrastructure management is simplified via the root `Makefile`. Follow these steps to deploy or update the cluster.

### 1. Prerequisites
- **GCP Project**: You must have a GCP project and be authenticated via `gcloud auth login`.
- **Terraform State Bucket**: Ensure the GCS bucket defined in `envs/dev/backend.tf` exists.
- **Variables**: Setup your local configuration.
  ```bash
  cp envs/dev/terraform.tfvars.example envs/dev/terraform.tfvars
  # Ensure project_id is set correctly in terraform.tfvars
  ```

### 2. Deployment Workflow
You can use the root `Makefile` (recommended) or run the commands manually.

#### Option A: Using Makefile (From Project Root)
| Command | Action |
| :--- | :--- |
| `make tf-init` | Initialize Terraform and download providers. |
| `make tf-plan` | Preview changes before applying. |
| `make tf-apply` | Provision/update the infrastructure. |

#### Option B: Manual CLI (From `terraform/envs/dev`)
If you prefer running Terraform directly, navigate to the environment directory:
```bash
cd terraform/envs/dev

# 1. Initialize
terraform init

# 2. Preview changes
terraform plan -var-file=terraform.tfvars

# 3. Deploy
terraform apply -var-file=terraform.tfvars
```

---

## 🏗️ Infrastructure Specs
- **Region**: `asia-east2` (Hong Kong) - optimized for latency.
- **Compute**: All node pools (`infra`, `compute`, `query`) utilize **Spot VMs** for maximum cost savings.
- **Scaling**: Node pools are currently set to scale from **0 to 1** node. Update `min_node_count` / `max_node_count` in `modules/gke/main.tf` to activate more nodes.
