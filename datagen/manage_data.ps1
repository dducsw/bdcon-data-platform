param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("seed-snapshot", "gendata", "resume-gendata", "gendata-once", "reset-seed-gendata", "full-load-gcs")]
    [string]$Action = "seed-snapshot",

    [string]$PG_HOST = "localhost",
    [int]$PG_PORT = 5433,
    [string]$PG_DB = "thelook_db",
    [string]$PG_USER = "db_user",
    [string]$PG_PASSWORD = "db_password",
    [string]$PG_SCHEMA = "demo",
    [int]$YEAR_SHIFT = 3,
    [switch]$IncludeEvents = $false,
    [string]$PYTHON = "python"
)

Write-Host "`n--- TheLook Data Management ($Action) ---" -ForegroundColor Cyan

$SkipEventsFlag = if ($IncludeEvents) { "" } else { "--skip-events" }

switch ($Action) {
    "seed-snapshot" {
        Write-Host " Running Seed from CSV with Time Shift..." -ForegroundColor Yellow
        if (-not $IncludeEvents) { Write-Host " (Skipping events table to save time)" -ForegroundColor Gray }
        & $PYTHON seed_from_csv.py --host $PG_HOST --port $PG_PORT --database $PG_DB --user $PG_USER --password $PG_PASSWORD --schema $PG_SCHEMA --data-dir ./data --truncate-first --year-shift $YEAR_SHIFT $SkipEventsFlag
    }

    "reset-seed-gendata" {
        Write-Host " Resetting Data and Starting Generator..." -ForegroundColor Yellow
        Write-Host " Step 1: Seeding CSV..." -ForegroundColor Gray
        if (-not $IncludeEvents) { Write-Host " (Skipping events table to save time)" -ForegroundColor Gray }
        & $PYTHON seed_from_csv.py --host $PG_HOST --port $PG_PORT --database $PG_DB --user $PG_USER --password $PG_PASSWORD --schema $PG_SCHEMA --data-dir ./data --truncate-first --year-shift $YEAR_SHIFT $SkipEventsFlag
        
        Write-Host " Step 2: Starting Generator..." -ForegroundColor Gray
        & $PYTHON thelook-ecomm/generator.py --db-host $PG_HOST --db-port $PG_PORT --db-user $PG_USER --db-password $PG_PASSWORD --db-name $PG_DB --db-schema $PG_SCHEMA --avg-qps 5 --init-num-users 1000 --max-iter -1 --publish-kafka
    }

    "gendata" {
        Write-Host " Starting Generator (1000 initial users)..." -ForegroundColor Yellow
        & $PYTHON thelook-ecomm/generator.py --db-host $PG_HOST --db-port $PG_PORT --db-user $PG_USER --db-password $PG_PASSWORD --db-name $PG_DB --db-schema $PG_SCHEMA --avg-qps 5 --init-num-users 1000 --max-iter -1 --publish-kafka
    }

    "resume-gendata" {
        Write-Host " Resuming Generator (0 initial users)..." -ForegroundColor Yellow
        & $PYTHON thelook-ecomm/generator.py --db-host $PG_HOST --db-port $PG_PORT --db-user $PG_USER --db-password $PG_PASSWORD --db-name $PG_DB --db-schema $PG_SCHEMA --avg-qps 5 --init-num-users 0 --max-iter -1 --publish-kafka
    }

    "gendata-once" {
        Write-Host " Running Generator for 100 iterations..." -ForegroundColor Yellow
        & $PYTHON thelook-ecomm/generator.py --db-host $PG_HOST --db-port $PG_PORT --db-user $PG_USER --db-password $PG_PASSWORD --db-name $PG_DB --db-schema $PG_SCHEMA --avg-qps 5 --init-num-users 0 --max-iter 100 --publish-kafka
    }

    "full-load-gcs" {
        Write-Host " Running Full Load to GCS..." -ForegroundColor Yellow
        & $PYTHON ../src/etl/local_pg_to_gcs.py --pg-host $PG_HOST --pg-port $PG_PORT --pg-database $PG_DB --pg-user $PG_USER --pg-password $PG_PASSWORD --pg-schema $PG_SCHEMA
    }
}

Write-Host "`n Operation $Action completed." -ForegroundColor Green
