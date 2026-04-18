$ErrorActionPreference = "Continue"

$ZONE = "asia-east1-a"
$CLUSTER = "data-platform-cluster"
$PROJECT = "k8s-data-platform-1879"

function Write-Step([string]$msg) {
    Write-Host "`n$msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Info([string]$msg) {
    Write-Host "  --> $msg" -ForegroundColor Yellow
}

function Get-PodRows([string]$namespace) {
    $json = kubectl get pods -n $namespace -o json 2>$null
    if (-not $json) {
        return @()
    }

    $items = ($json | ConvertFrom-Json).items
    if (-not $items) {
        return @()
    }

    return @($items | ForEach-Object {
        [PSCustomObject]@{
            Name = $_.metadata.name
            Phase = $_.status.phase
            DeletionTimestamp = $_.metadata.deletionTimestamp
        }
    })
}

function Wait-WorkloadsGone([string]$namespace, [string[]]$expectedPrefixes, [int]$timeoutSec = 180) {
    if (-not $expectedPrefixes -or $expectedPrefixes.Count -eq 0) {
        return
    }

    Write-Info "Waiting for scaled workloads in '$namespace' to disappear (timeout ${timeoutSec}s)..."
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        $matching = @(Get-PodRows -namespace $namespace | Where-Object {
            $podName = $_.Name
            foreach ($prefix in $expectedPrefixes) {
                if ($podName -like "$prefix*") {
                    return $true
                }
            }
            return $false
        })

        if (-not $matching) {
            Write-Ok "Scaled workloads are gone from '$namespace'."
            return
        }

        $summary = ($matching | Select-Object -ExpandProperty Name) -join ", "
        Write-Info "Still present in '$namespace': $summary"
        Start-Sleep -Seconds 5
        $elapsed += 5
    }

    Write-Host "  [WARN] Some scaled workloads are still present in '$namespace' after ${timeoutSec}s." -ForegroundColor Red
}

function Remove-StuckPods([string]$namespace, [string[]]$expectedPrefixes, [int]$graceSeconds = 0) {
    if (-not $expectedPrefixes -or $expectedPrefixes.Count -eq 0) {
        return
    }

    $matching = @(Get-PodRows -namespace $namespace | Where-Object {
        $podName = $_.Name
        foreach ($prefix in $expectedPrefixes) {
            if ($podName -like "$prefix*") {
                return $true
            }
        }
        return $false
    })

    foreach ($pod in $matching) {
        Write-Info "Force deleting stuck pod '$($pod.Name)' in '$namespace'..."
        kubectl delete pod $pod.Name -n $namespace --force --grace-period=$graceSeconds 2>$null | Out-Null
    }
}

function Wait-NodePoolSize([string]$nodePool, [int]$expectedSize = 0, [int]$timeoutSec = 300) {
    Write-Info "Waiting for node pool '$nodePool' to reach $expectedSize node(s)..."
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        $size = gcloud container node-pools describe $nodePool `
            --cluster $CLUSTER `
            --zone $ZONE `
            --project $PROJECT `
            --format="value(initialNodeCount)" 2>$null

        if ($size -eq "$expectedSize") {
            Write-Ok "Node pool '$nodePool' is now at $expectedSize node(s)."
            return
        }

        Start-Sleep -Seconds 10
        $elapsed += 10
    }

    Write-Host "  [WARN] Node pool '$nodePool' did not report size $expectedSize within ${timeoutSec}s." -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Red
Write-Host "   FAST SHUTDOWN - DATA PLATFORM CLUSTER (MAX SAVINGS)    " -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red
Write-Host "  Cluster : $CLUSTER"
Write-Host "  Zone    : $ZONE"
Write-Host "  Project : $PROJECT"
Write-Host ""

$namespacesToClean = @("data-platform", "monitoring", "ingress-nginx", "external-secrets")
$scaledPodsByNamespace = @{
    "data-platform" = @(
        "trino-coordinator", "trino-worker",
        "spark-operator-controller",
        "superset",
        "airflow-scheduler", "airflow-dag-processor", "airflow-api-server", "airflow-statsd", "airflow-triggerer",
        "gravitino",
        "kafka-exporter", "redis-exporter",
        "data-platform-kafka-entity-operator",
        "data-platform-kafka-broker-pool",
        "data-platform-kafka-controller-pool",
        "minio", "postgres", "redis", "hive-metastore"
    )
    "monitoring" = @(
        "kube-prometheus-stack-grafana",
        "kube-prometheus-stack-kube-state-metrics",
        "kube-prometheus-stack-operator",
        "alertmanager-kube-prometheus-stack-alertmanager",
        "prometheus-kube-prometheus-stack-prometheus"
    )
    "external-secrets" = @(
        "external-secrets",
        "external-secrets-cert-controller",
        "external-secrets-webhook"
    )
    "ingress-nginx" = @(
        "ingress-nginx-controller"
    )
}

Write-Step "[1/6] Deleting PodDisruptionBudgets to unblock node drain..."
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

Write-Step "[2/6] Scaling down stateless workloads..."
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
kubectl scale deployment --all -n monitoring --replicas=0 2>$null | Out-Null
kubectl scale deployment --all -n external-secrets --replicas=0 2>$null | Out-Null
kubectl scale deployment --all -n ingress-nginx --replicas=0 2>$null | Out-Null
Write-Ok "Stateless workloads scaled to 0."

Write-Step "[3/6] Shutting down Kafka in ordered mode..."
kubectl scale deployment data-platform-kafka-entity-operator -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale kafkanodepool broker-pool -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale kafkanodepool controller-pool -n data-platform --replicas=0 2>$null | Out-Null
Write-Ok "Kafka scale-down commands sent."

Write-Step "[4/6] Scaling down stateful workloads..."
kubectl scale statefulset minio -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset postgres -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset redis -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset hive-metastore -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset airflow-triggerer -n data-platform --replicas=0 2>$null | Out-Null
kubectl scale statefulset --all -n monitoring --replicas=0 2>$null | Out-Null
Write-Ok "Stateful scale-down commands sent."

Write-Step "[5/6] Waiting for all scaled workloads to terminate..."
foreach ($ns in $namespacesToClean) {
    Wait-WorkloadsGone -namespace $ns -expectedPrefixes $scaledPodsByNamespace[$ns] -timeoutSec 180
}

Write-Info "Force deleting any remaining stuck workload pods before node resize..."
foreach ($ns in $namespacesToClean) {
    Remove-StuckPods -namespace $ns -expectedPrefixes $scaledPodsByNamespace[$ns]
}

foreach ($ns in $namespacesToClean) {
    Wait-WorkloadsGone -namespace $ns -expectedPrefixes $scaledPodsByNamespace[$ns] -timeoutSec 60
}

Write-Step "[6/6] Resizing node pools to 0..."
Write-Info "Removing infra-pool autoscaler min-node constraint..."
gcloud container clusters update $CLUSTER `
    --zone $ZONE `
    --node-pool infra-pool `
    --enable-autoscaling --min-nodes 0 --max-nodes 1 `
    --quiet

Write-Info "Resizing compute-pool to 0..."
gcloud container clusters resize $CLUSTER --node-pool compute-pool --num-nodes 0 --zone $ZONE --quiet
Wait-NodePoolSize -nodePool "compute-pool" -expectedSize 0 -timeoutSec 300

Write-Info "Resizing query-pool to 0..."
gcloud container clusters resize $CLUSTER --node-pool query-pool --num-nodes 0 --zone $ZONE --quiet
Wait-NodePoolSize -nodePool "query-pool" -expectedSize 0 -timeoutSec 300

Write-Info "Resizing infra-pool to 0..."
gcloud container clusters resize $CLUSTER --node-pool infra-pool --num-nodes 0 --zone $ZONE --quiet
Wait-NodePoolSize -nodePool "infra-pool" -expectedSize 0 -timeoutSec 600

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   CLUSTER FULLY SHUT DOWN - ZERO COMPUTE COST            " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  All node pools: 0 nodes"
Write-Host "  All workloads : 0 replicas"
Write-Host ""
Write-Host "  To restore cluster, run:" -ForegroundColor Yellow
Write-Host "    cd terraform/envs/dev && terraform apply -var-file=terraform.tfvars" -ForegroundColor Yellow
Write-Host "  Then redeploy workloads:" -ForegroundColor Yellow
Write-Host "    make k8s-dev" -ForegroundColor Yellow
Write-Host ""
