<#
.SYNOPSIS
  Deploys action-engine to Azure Container Apps and then proves it from outside.

.DESCRIPTION
  The runbook in deploy/README.md, as a script, because the operator's shell is
  Windows PowerShell 5.1 and the Azure docs are written in bash continuations
  that do not survive a paste into it.

  Secrets are never arguments and are never printed. The script reads them from
  two environment variables that the operator sets in their own shell, hands
  them to the Azure secret store, and forgets them. Nothing here writes a secret
  to disk, to the repo, or to a transcript.

  Set them first, in your shell, not in a file:

      $env:ACTION_ENGINE_JWT_SECRET  = "<48+ random chars>"
      $env:ACTION_ENGINE_DATABASE_URL = "<the Neon pooled connection string>"

  Generate the signing key with:

      py -c "import secrets; print(secrets.token_urlsafe(48))"

.PARAMETER VerifyOnly
  Skip every change and just re-run the three checks against the live URL.
  Safe to run any time; this is also what to run before quoting a number.

.EXAMPLE
  .\deploy\deploy.ps1
.EXAMPLE
  .\deploy\deploy.ps1 -VerifyOnly
#>
[CmdletBinding()]
param(
    [string] $ResourceGroup = "anubis-lab",
    [string] $AppName       = "action-engine",
    [string] $Location      = "centralindia",
    [string] $Image         = "ghcr.io/quantummonkey/action-engine:latest",
    [int]    $MaxReplicas   = 2,
    [switch] $VerifyOnly
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Native stderr is never redirected anywhere in this script. Under
# $ErrorActionPreference = "Stop", Windows PowerShell 5.1 turns a redirected
# native stderr line into a terminating NativeCommandError even when the exit
# code is 0, which would fail the script on az's ordinary warnings. So az writes
# its own errors straight to the console and only $LASTEXITCODE is trusted.
function Invoke-Az {
    param([string[]] $AzArgs, [string] $What)
    Write-Host "  az $($AzArgs -join ' ')" -ForegroundColor DarkGray
    $out = & az @AzArgs
    if ($LASTEXITCODE -ne 0) { throw "$What failed (az exit $LASTEXITCODE)" }
    return $out
}

# Same, but the arguments carry secret values, so they are not echoed.
function Invoke-AzQuiet {
    param([string[]] $AzArgs, [string] $What)
    Write-Host "  az $($AzArgs[0..2] -join ' ') ... (rest hidden: it carries secrets)" -ForegroundColor DarkGray
    $out = & az @AzArgs
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed (az exit $LASTEXITCODE). az printed the reason above; if it echoed a value, that value is now on your screen only."
    }
    return $out
}

function Get-HttpStatus {
    param([string] $Url)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 60
        return [int] $r.StatusCode
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { return [int] $_.Exception.Response.StatusCode }
        throw
    }
}

# ---------------------------------------------------------------- preflight --
Write-Host "`n== 0. Preflight ==" -ForegroundColor Cyan

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "The Azure CLI is not installed. Install it, open a NEW shell, then re-run:`n" +
          "    winget install -e --id Microsoft.AzureCLI"
}

$account = & az account show --output json
if ($LASTEXITCODE -ne 0) { throw "Not logged in. Run 'az login' first." }
$sub = ($account | ConvertFrom-Json)
Write-Host ("  subscription: {0} ({1})" -f $sub.name, $sub.id)

if (-not $VerifyOnly) {
    foreach ($v in @("ACTION_ENGINE_JWT_SECRET", "ACTION_ENGINE_DATABASE_URL")) {
        $val = [Environment]::GetEnvironmentVariable($v, "Process")
        if ([string]::IsNullOrWhiteSpace($val)) { throw "$v is not set in this shell. See the header of this script." }
    }
    $jwt = $env:ACTION_ENGINE_JWT_SECRET
    if ($jwt.Length -lt 32) { throw "ACTION_ENGINE_JWT_SECRET is $($jwt.Length) chars; HS256 wants 32 or more." }
    Write-Host "  both secrets present, lengths look sane (values not shown)"
}

# ------------------------------------------------------------------ deploy --
if (-not $VerifyOnly) {
    Write-Host "`n== 1. Resource group ==" -ForegroundColor Cyan
    Invoke-Az @("group", "create", "--name", $ResourceGroup, "--location", $Location, "--output", "none") "group create"

    Write-Host "`n== 2. The app ==" -ForegroundColor Cyan
    Write-Host "  first run creates a Container Apps environment too; allow a few minutes." -ForegroundColor DarkGray
    Invoke-Az @(
        "containerapp", "up",
        "--name", $AppName,
        "--resource-group", $ResourceGroup,
        "--location", $Location,
        "--image", $Image,
        "--target-port", "8000",
        "--ingress", "external"
    ) "containerapp up"

    Write-Host "`n== 3. Secrets and settings ==" -ForegroundColor Cyan
    Invoke-AzQuiet @(
        "containerapp", "secret", "set",
        "--name", $AppName, "--resource-group", $ResourceGroup, "--output", "none",
        "--secrets",
        "jwt-secret=$($env:ACTION_ENGINE_JWT_SECRET)",
        "database-url=$($env:ACTION_ENGINE_DATABASE_URL)"
    ) "secret set"

    # min-replicas 0 is the default for an HTTP app, which is what keeps the bill
    # at zero; max-replicas is the ceiling, and it is the half worth stating.
    Invoke-Az @(
        "containerapp", "update",
        "--name", $AppName, "--resource-group", $ResourceGroup, "--output", "none",
        "--min-replicas", "0", "--max-replicas", "$MaxReplicas",
        "--set-env-vars",
        "ACTION_ENGINE_JWT_SECRET=secretref:jwt-secret",
        "ACTION_ENGINE_DATABASE_URL=secretref:database-url",
        "ACTION_ENGINE_RATE_LIMIT=60",
        "ACTION_ENGINE_RATE_WINDOW=60"
    ) "containerapp update"
}

# ------------------------------------------------------------------ verify --
Write-Host "`n== 4. Prove it to a stranger ==" -ForegroundColor Cyan

$fqdn = (Invoke-Az @(
    "containerapp", "show", "--name", $AppName, "--resource-group", $ResourceGroup,
    "--query", "properties.configuration.ingress.fqdn", "--output", "tsv"
) "containerapp show") | Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($fqdn)) { throw "No ingress FQDN. Ingress is probably not external." }
$base = "https://$fqdn"
Write-Host "  URL: $base`n"

# The first request after an idle period pays the cold start; that is the trade.
Write-Host "  warming (min-replicas is 0, so the first call wakes it)..." -ForegroundColor DarkGray
$null = Get-HttpStatus "$base/healthz"

$checks = @(
    @{ Name = "healthz is open";                Url = "$base/healthz";     Expect = 200 },
    @{ Name = "the generated contract";         Url = "$base/openapi.json"; Expect = 200 },
    @{ Name = "anonymous is refused, not served"; Url = "$base/v1/tables";  Expect = 401 }
)

$failed = 0
foreach ($c in $checks) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $code = Get-HttpStatus $c.Url
    $sw.Stop()
    $ok = ($code -eq $c.Expect)
    if (-not $ok) { $failed++ }
    $mark = if ($ok) { "PASS" } else { "FAIL" }
    $colour = if ($ok) { "Green" } else { "Red" }
    Write-Host ("  [{0}] {1,-30} {2} (want {3})  {4} ms" -f $mark, $c.Name, $code, $c.Expect, $sw.ElapsedMilliseconds) -ForegroundColor $colour
}

Write-Host ""
if ($failed -gt 0) {
    Write-Host "$failed of $($checks.Count) checks failed. Read the logs before changing anything:" -ForegroundColor Red
    Write-Host "  az containerapp logs show --name $AppName --resource-group $ResourceGroup --follow"
    exit 1
}

Write-Host "All $($checks.Count) checks pass. REQ-16 is done." -ForegroundColor Green
Write-Host ""
Write-Host "Next, and only now:"
Write-Host "  1. Put $base in the action-engine README and in the Featured link."
Write-Host "  2. Move API Development, Systems Integration, PostgreSQL, Docker, CI/CD,"
Write-Host "     Cloud Computing and Microsoft Azure from CLAIMED to SHOWN in"
Write-Host "     money-map/sends/skills/COVERAGE.tsv, then rebuild the proof index."
Write-Host "  3. The post needs a number, not an adjective: the URL, the latency above,"
Write-Host "     and the test count."
Write-Host ""
Write-Host "To stop every meter attached to this: az group delete --name $ResourceGroup --yes --no-wait" -ForegroundColor DarkGray
