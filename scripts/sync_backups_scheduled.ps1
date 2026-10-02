$ErrorActionPreference = "Stop"

$LocalBackupDir = Join-Path $env:USERPROFILE "BloguitoBackups"
$LogPath = Join-Path $LocalBackupDir "sync.log"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot "agent-publisher\.venv\Scripts\python.exe"
$SyncScript = Join-Path $PSScriptRoot "sync_backups.py"
New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom

function Add-Utf8Line {
    param([string]$Path, [string]$Value)
    [System.IO.File]::AppendAllText($Path, $Value + [Environment]::NewLine, $Utf8NoBom)
}

function Write-BackupLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Utf8Line -Path $LogPath -Value "[$timestamp] $Message"
}

Write-BackupLog "Scheduled backup sync started."

try {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Project Python runtime not found: $Python"
    }
    if (-not (Test-Path -LiteralPath $SyncScript -PathType Leaf)) {
        throw "Direct backup sync script not found: $SyncScript"
    }

    $env:BLOGUITO_BACKUP_SSH_HOST = "bloguito"
    $env:BLOGUITO_BACKUP_LOCAL_DIR = $LocalBackupDir
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    & $Python $SyncScript 2>&1 | ForEach-Object {
        Add-Utf8Line -Path $LogPath -Value ([string]$_)
        Write-Output $_
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Direct SSH backup sync exited with code $LASTEXITCODE"
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
