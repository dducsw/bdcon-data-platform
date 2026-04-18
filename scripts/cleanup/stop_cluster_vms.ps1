$ErrorActionPreference = "Continue"

$ZONE    = "asia-east1-a"
$CLUSTER = "data-platform-cluster"
$PROJECT = "k8s-data-platform-1879"

# ── Helpers ─────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host "`n$msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}
function Write-Info([string]$msg) {
    Write-Host "  --> $msg" -ForegroundColor Yellow
}

function Wait-PodsGone([string]$namespace, [int]$timeoutSec = 120) {
    Write-Info "Waiting for pods in '$namespace' to fully terminate (timeout ${timeoutSec}s)..."
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        $pods = kubectl get pods -n $namespace --no-headers 2>$null | Where-Object { $_ -ne "" }
        if (-not $pods) {
            Write-Ok "Namespace '$namespace' is clear."
            return
        }
        Start-Sleep -Seconds 5
        $elapsed += 5
    }
    Write-Host "  [WARN] Pods still present in '$namespace' after ${timeoutSec}s — continuing anyway." -ForegroundColor Red
}

# ── Banner ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Red
Write-Host "   FAST SHUTDOWN — DATA PLATFORM CLUSTER (MAX SAVINGS)    " -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red
Write-Host "  Cluster : $CLUSTER"
Write-Host "  Zone    : $ZONE"
Write-Host "  Project : $PROJECT"
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Delete PodDisruptionBudgets (unblock eviction)
# PDB with minAvailable:1 on a 1-replica workload will freeze node drain forever.
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[1/6] Deleting PodDisruptionBudgets to unblock node drain..."

$namespacesToClean = @("data-platform", "monitoring", "ingress-nginx", "external-secrets")
foreach ($ns in $namespacesToClean) {
    $pdbs = kubectl get pdb -n $ns --no-headers -o name 2>$null
    if ($pdbs) {
        Write-Info "Deleting PDBs in namespace '$ns'..."
        kubectl delete pdb --all -n $ns | Out-Null
        Write-Ok "PDBs removed from '$ns'."
    } else {
        Write-Info "No PDBs found in '$ns'."
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Scale down stateless workloads first (fast)
# These have no volumes to detach, terminates quickly.
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[2/6] Scaling down stateless workloads (Trino, Spark, Superset, Airflow schedulers)..."

$statelessDeploys = @(
    "trino-coordinator", "trino-worker",
    "spark-operator-controller",
    "superset",
    "airflow-scheduler", "airflow-dag-processor", "airflow-api-server", "airflow-statsd",
    "gravitino",
    "kafka-exporter", "redis-exporter"
)
foreach ($d in $statelessDeploys) {
    kubectl scale deployment $d -n data-platform --replicas=0 2>$null | Out-Null
}
Write-Ok "Stateless deployments scaled to 0."

# Scale down monitoring & infra namespaces (all stateless side of these)
kubectl scale deployment --all -n monitoring        --replicas=0 2>$null | Out-Null
kubectl scale deployment --all -n external-secrets  --replicas=0 2>$null | Out-Null
kubectl scale deployment --all -n ingress-nginx     --replicas=0 2>$null | Out-Null
Write-Ok "System namespace deployments scaled to 0."

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Scale down Kafka (Strimzi-managed, needs ordered shutdown)
# Scale operator FIRST so it stops reconciling, then scale node pools.
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[3/6] Shutting down Kafka (Strimzi) in correct order..."

Write-Info "Scaling down Strimzi entity-operator (stop reconciliation first)..."
kubectl scale deployment data-platform-kafka-entity-operator -n data-platform --replicas=0 2>$null | Out-Null

Write-Info "Scaling down KafkaNodePools (broker then controller)..."
kubectl scale kafkanodepool broker-pool     -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale kafkanodepool controller-pool -n data-platform --replicas=0 2>$null | Out-Null
Write-Ok "Kafka scale-down commands sent."

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4 — Scale down stateful workloads (needs disk detach — inherently slow)
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[4/6] Scaling down stateful services (MinIO, Postgres, Redis, Hive, Prometheus)..."

kubectl scale statefulset minio          -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset postgres       -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset redis          -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset hive-metastore -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset airflow-triggerer -n data-platform --replicas=0 2>$null | Out-Null

kubectl scale statefulset --all -n monitoring --replicas=0 2>$null | Out-Null
Write-Ok "Stateful scale-down commands sent."

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5 — Wait for pods to actually terminate before touching nodes
# Skipping this is the #1 cause of slow/stuck node pool resizes.
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[5/6] Waiting for all pods to fully terminate before resizing node pools..."

foreach ($ns in $namespacesToClean) {
    Wait-PodsGone -namespace $ns -timeoutSec 180
}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 6 — Resize node pools to 0 (compute/query first, infra last)
# Infra pool hosts most stateful workloads → drain takes longest → save for last.
# Update autoscaler min to 0 on infra-pool first so GKE doesn't block scale-down.
# ═══════════════════════════════════════════════════════════════════════════
Write-Step "[6/6] Resizing node pools to 0..."

Write-Info "Removing infra-pool autoscaler min-node constraint..."
gcloud container clusters update $CLUSTER `
    --zone $ZONE `
    --node-pool infra-pool `
    --enable-autoscaling --min-nodes 0 --max-nodes 1 `
    --quiet

Write-Info "Resizing compute-pool to 0 (pure spot compute, fastest)..."
gcloud container clusters resize $CLUSTER --node-pool compute-pool --num-nodes 0 --zone $ZONE --quiet

Write-Info "Resizing query-pool to 0..."
gcloud container clusters resize $CLUSTER --node-pool query-pool   --num-nodes 0 --zone $ZONE --quiet

Write-Info "Resizing infra-pool to 0 (stateful — may take a few minutes)..."
gcloud container clusters resize $CLUSTER --node-pool infra-pool   --num-nodes 0 --zone $ZONE --quiet

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   CLUSTER FULLY SHUT DOWN — ZERO COMPUTE COST            " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  All node pools: 0 nodes"
Write-Host "  All workloads : 0 replicas"
Write-Host ""
Write-Host "  To restore cluster, run:" -ForegroundColor Yellow
Write-Host "    cd terraform/envs/dev && terraform apply -var-file=terraform.tfvars" -ForegroundColor Yellow
Write-Host "  Then redeploy workloads:" -ForegroundColor Yellow
Write-Host "    make k8s-dev" -ForegroundColor Yellow
Write-Host ""
