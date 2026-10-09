param([switch]$Strict)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$expected = '077539a25c49e67bc6f75bc36aa9ecb70557125f'
$sha = 'a99a68cd14757f5575c6445c228da58d27c151494f8a92ea2f355538b1c58b84'
$files = @('release-manifest.json','PC_AGENT_PROMPT.md','pc-test/compose.locktest.yml','pc-test/pc_lock_test.py')
$errors = New-Object System.Collections.Generic.List[string]
foreach ($name in $files) {
  $path = Join-Path $root $name
  if (!(Test-Path -LiteralPath $path)) { $errors.Add('Missing: ' + $name) }
}
if (Test-Path (Join-Path $root 'release-manifest.json')) {
  $actual = (Get-FileHash -LiteralPath (Join-Path $root 'release-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
  Write-Output ('Release manifest SHA256 verified: ' + ($actual -eq $sha))
  if ($actual -ne $sha) { $errors.Add('Release manifest SHA256 mismatch') }
}
try {
  $version = (& git --version | Out-String).Trim(); Write-Output $version
  $repo = (Resolve-Path (Join-Path $root '..')).Path
  $rev = (& git -C $repo rev-parse --verify ($expected+'^{commit}') 2>$null | Out-String).Trim()
  if ($rev -ne $expected) { $errors.Add('Verified release commit not in this Git checkout') }
} catch { $errors.Add('Git unavailable or missing verified release commit') }
try {
  $docker = Get-Command docker -ErrorAction Stop
  $version = (& docker --version | Out-String).Trim(); Write-Output $version
  & docker compose version
  if ($LASTEXITCODE -ne 0) { $errors.Add('Docker Compose unavailable') }
  $contextJson = & docker context inspect
  if ($LASTEXITCODE -ne 0) { $errors.Add('Docker context unavailable') }
  else {
    $ctx = $contextJson | ConvertFrom-Json
    $endpoint = [string]$ctx[0].Endpoints.docker.Host
    # Do NOT run against SSH/TCP remote engines, especially production.
    if ($endpoint -notmatch '^(npipe:|unix:)') { $errors.Add('Docker engine is not local: ' + $endpoint) }
    else { Write-Output ('Docker local context: ' + $ctx[0].Name) }
    $os = (& docker info --format '{{.OSType}}' | Out-String).Trim()
    if ($os -ne 'linux') { $errors.Add('Docker must be running Linux containers; observed: ' + $os) }
  }
} catch { $errors.Add('Docker not installed/running or access denied') }
try {
  $m = Get-CimInstance Win32_OperatingSystem
  Write-Output ('Host RAM GiB: ' + [math]::Round($m.TotalVisibleMemorySize/1MB,1))
  Write-Output ('Free RAM GiB: ' + [math]::Round($m.FreePhysicalMemory/1MB,1))
  if ($m.FreePhysicalMemory -lt 4MB) { $errors.Add('Free RAM under 4 GiB; do not start isolated DB/WordPress') }
} catch { Write-Output 'RAM check unavailable; agent must verify manually.' }
Write-Output ('Expected commit: ' + $expected)
if ($errors.Count -gt 0) {
  Write-Output 'PREFLIGHT_BLOCKED:'
  $errors | ForEach-Object { Write-Output (' - ' + $_) }
  if ($Strict) { exit 2 }
} else { Write-Output 'PREFLIGHT_PASS (no test containers started)' }
