$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$configPath = Join-Path $repoRoot "middleware\\config.yaml"
$configExamplePath = Join-Path $repoRoot "middleware\\config.example.yaml"

Push-Location $repoRoot
try {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0 -or !(Test-Path $venvPython)) {
        throw "Failed to create .venv."
    }

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in .venv."
    }

    & $venvPython -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install dependencies into .venv."
    }

    if (!(Test-Path $configPath)) {
        Copy-Item $configExamplePath $configPath
    }

    Write-Output "Environment ready (.venv)"
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    [Console]::Error.WriteLine("Setup failed. If venv bootstrap fails with ensurepip/temp permission errors, run from an unrestricted shell with a writable TEMP directory.")
    exit 1
}
finally {
    Pop-Location
}
