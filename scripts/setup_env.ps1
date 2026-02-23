python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
if (!(Test-Path middleware/config.yaml)) { Copy-Item middleware/config.example.yaml middleware/config.yaml }
Write-Output "Environment ready"
