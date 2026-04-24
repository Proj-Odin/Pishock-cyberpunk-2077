$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$configPath = Join-Path $repoRoot "middleware\\config.yaml"
$configExamplePath = Join-Path $repoRoot "middleware\\config.example.yaml"
$pythonCommand = $null
$pythonPrefixArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonPrefixArgs = @("-3")
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
}
else {
    throw "Python 3 was not found. Install Python 3 and make either 'py' or 'python' available on PATH."
}

Push-Location $repoRoot
try {
    & $pythonCommand @pythonPrefixArgs -m venv .venv
    if ($LASTEXITCODE -ne 0 -or !(Test-Path $venvPython)) {
        throw "Failed to create .venv."
    }

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in .venv."
    }

    & $venvPython -m pip install -r requirements.txt
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
