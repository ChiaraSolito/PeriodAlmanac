# Copies the newest database backup from the server to this PC over Tailscale (off-site copy).
#
#   .\scripts\pull_backup.ps1            # pull now
#   .\scripts\pull_backup.ps1 -Install   # register a weekly Windows scheduled task (Sundays 20:00)
#
# Requires: Tailscale running on this PC, and SSH key access to the server (see DEPLOY.md).
param(
    [string]$Server = "ubuntu@periodalmanac",
    [string]$RemoteDir = "PeriodAlmanac/data/backups",
    [string]$LocalDir = (Join-Path $env:USERPROFILE "Documents\PeriodAlmanac-backups"),
    [int]$Keep = 8,
    [switch]$Install
)
$ErrorActionPreference = "Stop"

if ($Install) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "20:00"
    # StartWhenAvailable: if the PC was off on Sunday evening, run at the next start-up.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable
    Register-ScheduledTask -TaskName "PeriodAlmanac backup" -Action $action -Trigger $trigger `
        -Settings $settings -Description "Copia settimanale del database PeriodAlmanac dal server" -Force | Out-Null
    Write-Host "Task 'PeriodAlmanac backup' registrato: ogni domenica alle 20:00."
    exit 0
}

New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
$log = Join-Path $LocalDir "pull.log"

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $log -Value $line
    Write-Host $line
}

# BatchMode: never prompt (the scheduled task has no console); fail instead.
$latest = ssh -o BatchMode=yes -o ConnectTimeout=20 $Server "ls -1t $RemoteDir/cycles-*.db 2>/dev/null | head -n 1"
if ($LASTEXITCODE -ne 0 -or -not $latest) {
    Write-Log "ERRORE: impossibile leggere i backup sul server (Tailscale attivo? chiave SSH?)"
    exit 1
}
$latest = $latest.Trim()
$name = Split-Path $latest -Leaf

scp -o BatchMode=yes -o ConnectTimeout=20 "${Server}:$latest" (Join-Path $LocalDir $name)
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERRORE: copia di $name fallita"
    exit 1
}

# Keep only the newest $Keep copies.
Get-ChildItem $LocalDir -Filter "cycles-*.db" | Sort-Object Name -Descending |
    Select-Object -Skip $Keep | Remove-Item -Force
Write-Log "OK: $name copiato in $LocalDir"
