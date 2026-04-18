param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("upload", "submit", "delete", "logs", "status", "redeploy")]
    [string]$Command,

    [string]$AppFile = "pipelines\spark_test_job.yaml",
    [string]$ScriptFile = "pipelines\spark_hive_minio_test.py",
    [string]$Namespace = "data-platform",
    [string]$MinioBucket = "datalake",
    [string]$MinioScriptDir = "scripts"
)

switch ($Command) {
    "upload" {
        $FileName = Split-Path $ScriptFile -Leaf
        Write-Host "[WAIT] Uploading script $FileName to MinIO (s3a://$MinioBucket/$MinioScriptDir/)..." -ForegroundColor Cyan
        cmd.exe /c "type $ScriptFile | kubectl exec -i -n $Namespace minio-0 -- mc pipe local/$MinioBucket/$MinioScriptDir/$FileName"
        Write-Host "[OK] Upload complete!" -ForegroundColor Green
    }
    "submit" {
        Write-Host "[WAIT] Submitting SparkApplication from $AppFile..." -ForegroundColor Cyan
        kubectl apply -f $AppFile -n $Namespace
        Write-Host "[INFO] Run .\spark.ps1 -Command status to watch progress or .\spark.ps1 -Command logs to view logs." -ForegroundColor Yellow
    }
    "delete" {
        Write-Host "[WAIT] Deleting SparkApplication..." -ForegroundColor Yellow
        kubectl delete -f $AppFile -n $Namespace --ignore-not-found
        Write-Host "[OK] Successfully deleted!" -ForegroundColor Green
    }
    "redeploy" {
        Write-Host "[START] Redeploying: Delete -> Upload -> Submit..." -ForegroundColor Cyan
        
        Write-Host "`n[1/3] Deleting old job..." -ForegroundColor Yellow
        kubectl delete -f $AppFile -n $Namespace --ignore-not-found

        $FileName = Split-Path $ScriptFile -Leaf
        Write-Host "`n[2/3] Uploading new script ($FileName)..." -ForegroundColor Yellow
        cmd.exe /c "type $ScriptFile | kubectl exec -i -n $Namespace minio-0 -- mc pipe local/$MinioBucket/$MinioScriptDir/$FileName"

        Write-Host "`n[3/3] Submitting new job..." -ForegroundColor Yellow
        kubectl apply -f $AppFile -n $Namespace

        Write-Host "`n[OK] Submitted! Waiting 5s for pod to appear..." -ForegroundColor Green
        Start-Sleep -Seconds 5
        Write-Host "[LOGS] Showing logs:" -ForegroundColor Cyan
        kubectl logs -n $Namespace -l spark-role=driver -f
    }
    "logs" {
        Write-Host "[LOGS] Tailing Spark Driver logs..." -ForegroundColor Cyan
        kubectl logs -n $Namespace -l spark-role=driver -f --tail=100
    }
    "status" {
        Write-Host "[STATUS] Watching Spark Job status (Ctrl+C to exit)..." -ForegroundColor Cyan
        kubectl get sparkapplication -n $Namespace -w
    }
}
