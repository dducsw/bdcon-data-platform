@echo off
SET Action=%1
if "%Action%"=="" SET Action=seed-snapshot

SET PG_HOST=localhost
SET PG_PORT=5433
SET PG_DB=thelook_db
SET PG_USER=db_user
SET PG_PASSWORD=db_password
SET PG_SCHEMA=demo
SET YEAR_SHIFT=3
SET PYTHON=python

echo --- TheLook Data Management (%Action%) ---

if "%Action%"=="seed-snapshot" (
    echo Running Seed from CSV with Time Shift...
    %PYTHON% seed_from_csv.py --host %PG_HOST% --port %PG_PORT% --database %PG_DB% --user %PG_USER% --password %PG_PASSWORD% --schema %PG_SCHEMA% --data-dir ./data --truncate-first --year-shift %YEAR_SHIFT%
) else if "%Action%"=="reset-seed-gendata" (
    echo Resetting Data and Starting Generator...
    %PYTHON% seed_from_csv.py --host %PG_HOST% --port %PG_PORT% --database %PG_DB% --user %PG_USER% --password %PG_PASSWORD% --schema %PG_SCHEMA% --data-dir ./data --truncate-first --year-shift %YEAR_SHIFT%
    %PYTHON% thelook-ecomm/generator.py --db-host %PG_HOST% --db-port %PG_PORT% --db-user %PG_USER% --db-password %PG_PASSWORD% --db-name %PG_DB% --db-schema %PG_SCHEMA% --avg-qps 5 --init-num-users 1000 --max-iter -1
) else if "%Action%"=="gendata" (
    echo Starting Generator...
    %PYTHON% thelook-ecomm/generator.py --db-host %PG_HOST% --db-port %PG_PORT% --db-user %PG_USER% --db-password %PG_PASSWORD% --db-name %PG_DB% --db-schema %PG_SCHEMA% --avg-qps 5 --init-num-users 1000 --max-iter -1
) else (
    echo Unknown action: %Action%
    echo Available: seed-snapshot, reset-seed-gendata, gendata, resume-gendata
)

pause
