[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env",
    [string]$ProjectName = "wardrowbe",
    [switch]$SkipBuild,
    [switch]$SkipBrowserInstall
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFiles = @(
    "-f", (Join-Path $repositoryRoot "docker-compose.yml"),
    "-f", (Join-Path $repositoryRoot "docker-compose.local.yml")
)
$composeArguments = @("compose", "-p", $ProjectName)

if ($EnvironmentFile) {
    $resolvedEnvironmentFile = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath(
        $EnvironmentFile
    )
    if (-not (Test-Path -LiteralPath $resolvedEnvironmentFile -PathType Leaf)) {
        throw "Environment file not found: $resolvedEnvironmentFile"
    }
    $composeArguments += @("--env-file", $resolvedEnvironmentFile)
}
$composeArguments += $composeFiles

Push-Location $repositoryRoot
try {
    if (-not $SkipBuild) {
        & docker @composeArguments build
        if ($LASTEXITCODE -ne 0) { throw "Docker image build failed" }
    }

    & docker @composeArguments up -d postgres redis
    if ($LASTEXITCODE -ne 0) { throw "Database or Redis startup failed" }

    & docker @composeArguments run --rm backend alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }

    & docker @composeArguments up -d
    if ($LASTEXITCODE -ne 0) { throw "Application startup failed" }

    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        try {
            $health = Invoke-RestMethod "http://localhost:8000/api/v1/health"
        }
        catch {
            $health = $null
        }
    } until ($health.status -eq "healthy" -or (Get-Date) -gt $deadline)
    if ($health.status -ne "healthy") { throw "Backend did not become healthy" }

    Push-Location (Join-Path $repositoryRoot "frontend")
    try {
        $nodeVersion = [Version]((& node --version).TrimStart("v"))
        $nodeSupported = (
            ($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19) -or
            ($nodeVersion.Major -eq 22 -and $nodeVersion.Minor -ge 12) -or
            $nodeVersion.Major -ge 24
        )
        if (-not $nodeSupported) {
            throw "Node.js 20.19+, 22.12+ or 24+ is required; found $nodeVersion"
        }
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
        if (-not $SkipBrowserInstall) {
            & npx playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "Chromium installation failed" }
        }
        & npm run smoke:full-stack
        if ($LASTEXITCODE -ne 0) { throw "Full-stack smoke failed" }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}
