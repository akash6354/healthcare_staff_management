# Windows equivalent of the Makefile targets.  Usage: pwsh scripts/dev.ps1 <target> [name]
param([Parameter(Mandatory = $true)][string]$Target, [string]$Name = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$compose = @("compose", "-f", "$root/infra/docker-compose.yml", "--env-file", "$root/.env")
function Api([string[]]$a) { Push-Location "$root/apps/api"; try { & uv run @a; if ($LASTEXITCODE) { exit $LASTEXITCODE } } finally { Pop-Location } }
switch ($Target) {
  "dev"          { & docker @compose up -d postgres redis s3 }
  "dev-full"     { & docker @compose --profile full up -d --build }
  "down"         { & docker @compose --profile full down }
  "migrate"      { Api @("alembic", "upgrade", "head") }
  "migrate-new"  { Api @("alembic", "revision", "-m", $Name) }
  "seed"         { Api @("python", "-m", "app.seed.sunrise") }
  "test"         { Api @("pytest"); & pnpm -r test }
  "test-api"     { Api @("pytest") }
  "lint"         { Api @("ruff", "check", "."); Api @("ruff", "format", "--check", "."); Api @("mypy", "app"); & pnpm -r lint; & pnpm -r typecheck }
  "verify-audit" { Api @("python", "-m", "app.audit.verify") }
  default        { Write-Error "Unknown target: $Target" }
}
