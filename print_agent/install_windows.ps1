# PoC installer script for Windows (requires admin)
$ErrorActionPreference = 'Stop'
Write-Host "Creating virtualenv and installing requirements..."
python -m venv .\venv
.\venv\Scripts\pip.exe install -r requirements.txt
Write-Host "To run the agent as a service consider using NSSM or create a scheduled task."
Write-Host "Start with: .\venv\Scripts\python.exe main.py"