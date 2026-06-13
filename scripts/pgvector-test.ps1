# Reproducible live pgvector memory test on Windows: docker up -> migrate -> test -> down.
#
#   ./scripts/pgvector-test.ps1            # bring up, test, tear down
#   $env:KEEP_UP = '1'; ./scripts/pgvector-test.ps1   # leave container running
#
# Requires Docker and the `db` extra installed (pip install -e ".[db]").
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $root 'deploy/docker-compose.pgvector-test.yml'
$dbUrl = 'postgresql+asyncpg://kaizen:kaizen@127.0.0.1:5433/kaizen'

# Prefer the project venv interpreter if present.
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

try {
    Write-Host '==> starting pgvector (deploy/docker-compose.pgvector-test.yml, host port 5433)'
    docker compose -f $compose up -d

    Write-Host '==> waiting for Postgres to accept connections'
    foreach ($i in 1..40) {
        docker exec kaizen-pgvector-test pg_isready -U kaizen -d kaizen *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 1
    }

    Write-Host '==> enabling the vector extension (migrate)'
    docker exec kaizen-pgvector-test psql -U kaizen -d kaizen -c 'CREATE EXTENSION IF NOT EXISTS vector;' *> $null

    Write-Host "==> running the integration suite against $dbUrl"
    $env:KAIZEN_TEST_DATABASE_URL = $dbUrl
    & $python -m pytest tests/integration -v
    $code = $LASTEXITCODE
}
finally {
    if ($env:KEEP_UP -eq '1') {
        Write-Host "==> KEEP_UP=1: leaving container up. URL: $dbUrl"
    } else {
        Write-Host '==> tearing down pgvector container'
        docker compose -f $compose down -v *> $null
    }
}
exit $code
