# Runs the Render version of OGLOS on this computer, exactly as Render would run it.
# Usage (PowerShell, from the project folder):   pwsh scripts/run-render-local.ps1
# Then open http://localhost:10000 (admin) and http://localhost:10000/staff/ (staff app).
# The demo logins are printed at the end. Stop it with:  docker stop oglos-render-test
param([switch]$Fresh)  # -Fresh wipes this copy's demo data and starts over
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "1/4 Making sure the database and Redis are running..."
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres redis | Out-Null
Start-Sleep -Seconds 3

Write-Host "2/4 Preparing a separate database for the Render copy..."
$sql = @"
DO `$`$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'render_owner') THEN
    CREATE ROLE render_owner LOGIN PASSWORD 'render-sim' CREATEROLE;
  END IF;
END `$`$;
"@
docker exec oglos-postgres-1 psql -U postgres -d oglos -qc $sql | Out-Null
if ($Fresh) { docker exec oglos-postgres-1 psql -U postgres -d oglos -qc "DROP DATABASE IF EXISTS oglos_render2" | Out-Null }
$exists = docker exec oglos-postgres-1 psql -U postgres -d oglos -tAc "SELECT 1 FROM pg_database WHERE datname='oglos_render2'"
if (-not $exists) { docker exec oglos-postgres-1 psql -U postgres -d oglos -qc "CREATE DATABASE oglos_render2 OWNER render_owner" | Out-Null }

Write-Host "3/4 Building the Render image (first time takes a few minutes)..."
docker build -q -f infra/render/Dockerfile -t oglos-render:test . | Out-Null

Write-Host "4/4 Starting it on port 10000..."
docker rm -f oglos-render-test 2>$null | Out-Null
$db = "postgres://render_owner:render-sim@host.docker.internal:5434/oglos_render2?sslmode=disable"
# Reuse the encryption key from .env: a new key on every run would make saved secrets unreadable.
$keyLine = Get-Content .env | Where-Object { $_ -match '^FIELD_ENCRYPTION_KEYS=' } | Select-Object -First 1
$keys = $keyLine.Substring('FIELD_ENCRYPTION_KEYS='.Length)
docker run -d --name oglos-render-test -p 10000:10000 `
  -e DATABASE_URL=$db -e MIGRATIONS_DATABASE_URL=$db -e PLATFORM_DATABASE_URL=$db `
  -e REDIS_URL=redis://host.docker.internal:6379/1 `
  -e JWT_SIGNING_KEY=local-render-signing-key-123456 -e HMAC_LOOKUP_KEY=local-render-lookup-key-1234 `
  -e OTP_HMAC_KEY=local-render-otp-key-12345678 -e QR_SIGNING_KEYS=v1:local-render-qr `
  -e "FIELD_ENCRYPTION_KEYS=$keys" -e EMAIL_PROVIDER=console oglos-render:test | Out-Null

for ($i = 0; $i -lt 90; $i++) {
  try { if ((Invoke-WebRequest -UseBasicParsing http://localhost:10000/api/v1/health).StatusCode -eq 200) { break } } catch { }
  Start-Sleep -Seconds 2
}
Write-Host ""
Write-Host "Ready:  admin  http://localhost:10000      staff app  http://localhost:10000/staff/"
Write-Host "Demo logins (hospital code SUNRISE):"
$ErrorActionPreference = "Continue"
(docker logs oglos-render-test 2>&1) | ForEach-Object { "$_" } | Select-String -CaseSensitive -Pattern "Admin  |MD  |Supervisor|Device key|PIN" | ForEach-Object { "  " + $_.Line.Trim() }
