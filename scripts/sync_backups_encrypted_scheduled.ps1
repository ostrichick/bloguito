$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot "agent-publisher\.venv\Scripts\python.exe"
$SyncScript = Join-Path $PSScriptRoot "sync_backups_encrypted.py"
$BackupDir = Join-Path $env:USERPROFILE "BloguitoBackupsEncrypted"
$KeyPath = Join-Path $env:USERPROFILE "Documents\Secure\Bloguito-Backup-Recovery.key"
$LogPath = Join-Path $BackupDir "sync.log"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
function Add-Log([string]$Message) {
    [System.IO.File]::AppendAllText(
        $LogPath,
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" + [Environment]::NewLine,
        $Utf8NoBom)
}

try {
    Add-Log "Encrypted backup sync started."
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Project Python runtime not found" }
    if (-not (Test-Path -LiteralPath $SyncScript -PathType Leaf)) { throw "Encrypted sync script not found" }
    if (-not (Test-Path -LiteralPath $KeyPath -PathType Leaf)) { throw "Recovery key not found" }
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    # Windows PowerShell 5.1 can promote a native process' stderr record to a
    # terminating error when ErrorActionPreference=Stop and stderr is merged
    # into a pipeline. Task Scheduler exposes that behavior more readily than
    # an interactive console. Let the native process finish, preserve all
    # output in the log, and use its real exit code as the success contract.
    $PriorErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $NativeOutput = @(& $Python $SyncScript --key $KeyPath --destination $BackupDir 2>&1)
        $NativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PriorErrorActionPreference
    }
    $NativeOutput | ForEach-Object { Add-Log ([string]$_) }
    if ($NativeExitCode -ne 0) { throw "Encrypted backup sync exited with code $NativeExitCode" }
    $cutoff = (Get-Date).AddDays(-30)
    Get-ChildItem -LiteralPath $BackupDir -File -Filter "bloguito_backup_*.tar.gz.blgenc" |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force
    Add-Log "Encrypted backup sync completed successfully."
    exit 0
}
catch {
    Add-Log ("Encrypted backup sync failed: " + $_.Exception.Message)
    exit 1
}
