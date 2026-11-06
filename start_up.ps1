# Starts the web app/API and the Telegram bot side by side. Ctrl+C stops both.
# Usage:  .\start_up.ps1
# (if scripts are blocked:  powershell -ExecutionPolicy Bypass -File .\start_up.ps1)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtualenv non trovato. Esegui: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}

if (-not (Test-Path "data\cycles.db")) {
    & $python scripts\import_csv.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$web = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" `
    -NoNewWindow -PassThru

# 0.0.0.0 is only the bind address (all interfaces): it is not a URL you can open.
$lanIps = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -ExpandProperty IPAddress
Write-Host ""
Write-Host "Web app su questo PC:   http://127.0.0.1:8000"
foreach ($ip in $lanIps) { Write-Host "Dal telefono (Wi-Fi):   http://${ip}:8000" }
Write-Host ""

try {
    $hasToken = (Test-Path ".env") -and (Select-String -Path ".env" -Pattern '^TELEGRAM_TOKEN=.+' -Quiet)
    if ($hasToken) {
        & $python -m app.bot
    }
    else {
        Write-Host "TELEGRAM_TOKEN non configurato: avvio solo la web app (vedi .env.example)."
        $web.WaitForExit()
    }
}
finally {
    # --reload spawns a child process, so kill the whole tree.
    if (-not $web.HasExited) {
        taskkill /PID $web.Id /T /F | Out-Null
    }
}
