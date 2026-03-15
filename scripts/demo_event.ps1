$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"

Push-Location $repoRoot
try {
    if (!(Test-Path $venvPython)) {
        & (Join-Path $repoRoot "scripts\\setup_env.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to prepare .venv."
        }
    }

    & $venvPython -m middleware.demo_event @args
}
finally {
    Pop-Location
}
