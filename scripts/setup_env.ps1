python -m venv .venv

$activateScript = ".\.venv\Scripts\Activate.ps1"

try {
    & $activateScript
} catch [System.Management.Automation.PSSecurityException] {
    Write-Warning "PowerShell execution policy blocked venv activation. Retrying for this process only."
    Set-ExecutionPolicy -Scope Process Bypass -Force
    & $activateScript
}

python -m pip install --upgrade pip
pip install -e .[dev]
if (!(Test-Path middleware/config.yaml)) { Copy-Item middleware/config.example.yaml middleware/config.yaml }
Write-Output "Environment ready"
