$ErrorActionPreference = "Stop"

$LocalBackupDir = Join-Path $env:USERPROFILE "BloguitoBackups"
$LogPath = Join-Path $LocalBackupDir "sync.log"
New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null

function Write-BackupLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogPath -Value "[$timestamp] $Message"
}

Write-BackupLog "Scheduled backup sync started."

try {
    $WslLocalBackupDir = "/mnt/c/Users/$env:USERNAME/BloguitoBackups"
    $WslSyncScript = "/mnt/c/Users/$env:USERNAME/OneDrive/Documents/Projects/Bloguito/scripts/sync_backups_tailscale.py"
    $TailscaleReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        $TailscaleStatus = & wsl.exe -d Ubuntu-24.04 -- tailscale status 2>$null
        if ($LASTEXITCODE -eq 0 -and $TailscaleStatus -match "bloguito-server") {
            $TailscaleReady = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $TailscaleReady) {
        throw "Tailscale did not become ready in WSL."
    }

    $WslCommand = "BLOGUITO_BACKUP_LOCAL_DIR='$WslLocalBackupDir' python3 '$WslSyncScript'"

    & wsl.exe -d Ubuntu-24.04 -- bash -lc $WslCommand 2>&1 | ForEach-Object {
        Add-Content -LiteralPath $LogPath -Value $_
        Write-Output $_
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Tailscale backup sync exited with code $LASTEXITCODE"
    }

    # Keep a local month of verified off-server snapshots. The server keeps its
    # own shorter rolling set, so this preserves a longer independent history.
    $cutoff = (Get-Date).AddDays(-30)
    Get-ChildItem -LiteralPath $LocalBackupDir -File -Filter "bloguito_backup_*.tar.gz" |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force

    Write-BackupLog "Scheduled backup sync completed successfully."
    exit 0
}
catch {
    Write-BackupLog ("Scheduled backup sync failed: " + $_.Exception.Message)
    exit 1
}
