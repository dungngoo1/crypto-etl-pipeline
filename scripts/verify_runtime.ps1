param(
    [switch]$StartPipeline,
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RuntimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EvidenceDir = Join-Path $RepoRoot ".local/runtime-$RuntimeStamp"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

function Invoke-DockerLogged {
    param([string]$Label, [string[]]$DockerArgs)
    $RuntimeLog = Join-Path $EvidenceDir "$Label.log"
    $RuntimeOutput = & docker @DockerArgs 2>&1
    $RuntimeCode = $LASTEXITCODE
    $RuntimeOutput | Out-String | Set-Content -Encoding UTF8 -LiteralPath $RuntimeLog
    if ($RuntimeCode -ne 0) {
        throw "Docker command '$Label' failed (exit $RuntimeCode). See $RuntimeLog"
    }
    return ($RuntimeOutput | Out-String)
}

Push-Location $RepoRoot
try {
    Invoke-DockerLogged -Label "docker-version" -DockerArgs @("version") | Write-Host
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".env"))) {
        throw "Create .env from .env.example and configure local credentials first. Do not send .env."
    }
    Invoke-DockerLogged -Label "compose-config-check" -DockerArgs @("compose", "config", "--quiet") | Out-Null
    if ($StartPipeline) {
        Invoke-DockerLogged -Label "compose-up-build" -DockerArgs @("compose", "up", "-d", "--build") | Write-Host
    }
    Invoke-DockerLogged -Label "compose-status" -DockerArgs @("compose", "ps", "-a") | Write-Host
    Invoke-DockerLogged -Label "airflow-init" -DockerArgs @("compose", "logs", "--no-color", "--tail", "150", "airflow-init") | Out-Null
    $RuntimeImports = Invoke-DockerLogged -Label "dag-import-errors" -DockerArgs @(
        "compose", "exec", "-T", "airflow-scheduler", "airflow", "dags", "list-import-errors", "--output", "json"
    )
    $RuntimeImports | Write-Host
    # Airflow can emit startup log lines before JSON. Keep the original output for review.
    if (-not $StartPipeline) {
        Write-Host "Read-only diagnostics saved to: $EvidenceDir"
        Write-Host "To build and verify a new DAG run: .\scripts\verify_runtime.ps1 -StartPipeline"
        return
    }
    $RuntimeRunId = "verify__$RuntimeStamp"
    Invoke-DockerLogged -Label "dag-unpause" -DockerArgs @(
        "compose", "exec", "-T", "airflow-scheduler", "airflow", "dags", "unpause", "crypto_medallion_elt_pipeline"
    ) | Out-Null
    Invoke-DockerLogged -Label "dag-trigger" -DockerArgs @(
        "compose", "exec", "-T", "airflow-scheduler", "airflow", "dags", "trigger",
        "--run-id", $RuntimeRunId, "crypto_medallion_elt_pipeline"
    ) | Write-Host
    $RuntimeDeadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $RuntimeSuccess = $false
    while ((Get-Date) -lt $RuntimeDeadline) {
        $RuntimeState = Invoke-DockerLogged -Label "dag-state" -DockerArgs @(
            "compose", "exec", "-T", "airflow-scheduler", "airflow", "dags", "state",
            "crypto_medallion_elt_pipeline", $RuntimeRunId
        )
        Write-Host $RuntimeState.Trim()
        if ($RuntimeState -match "(?m)^success\s*$") { $RuntimeSuccess = $true; break }
        if ($RuntimeState -match "(?m)^failed\s*$") { break }
        Start-Sleep -Seconds 10
    }
    Invoke-DockerLogged -Label "task-states" -DockerArgs @(
        "compose", "exec", "-T", "airflow-scheduler", "airflow", "tasks", "states-for-dag-run",
        "crypto_medallion_elt_pipeline", $RuntimeRunId, "--output", "json"
    ) | Write-Host
    Invoke-DockerLogged -Label "scheduler-tail" -DockerArgs @(
        "compose", "logs", "--no-color", "--tail", "150", "airflow-scheduler"
    ) | Out-Null
    if (-not $RuntimeSuccess) { throw "DAG did not succeed within the limit. See $EvidenceDir" }
    $RuntimeQuery = @"
SELECT p.batch_id, p.captured_at, p.published_at, b.ticker_count,
 (SELECT count(*) FROM bronze.raw_crypto_tickers r WHERE r.batch_id=p.batch_id) AS raw_rows,
 (SELECT count(*) FROM gold.fact_market_metrics f WHERE f.batch_id=p.batch_id) AS gold_rows,
 (SELECT count(*) FROM ga.latest_tickers) AS analytics_rows
FROM ga.publication_status p JOIN bronze.ingestion_batches b USING(batch_id);
"@
    $RuntimePsql = 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"'
    Invoke-DockerLogged -Label "published-data" -DockerArgs @(
        "compose", "exec", "-T", "postgres-warehouse", "sh", "-c", $RuntimePsql, "sh", $RuntimeQuery
    ) | Write-Host
    Write-Host "DAG success. Verify publication batch and counts in: $EvidenceDir"
    Write-Host "This script has not opened or refreshed Power BI Desktop."
}
finally {
    Pop-Location
}
