# Windows Task Scheduler entry point for the Aethon wrapper daemon
# (docs/superpowers/specs/2026-09-19-daemon-design.md, adapted for Task
# Scheduler instead of Oracle Cloud/cron per the author's decision on
# 2026-09-20 -- card-verification friction on Oracle's signup flow).
# Task Scheduler can run with a minimal environment, so this script sets
# PATH explicitly rather than relying on it being inherited, and loads
# .env directly rather than assuming a shell profile sourced it.

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$env:PATH = "C:\Users\FEYISAYO ATINUKE\.local\bin;C:\Program Files\nodejs;$env:PATH"

Get-Content "$RepoRoot\.env" | Where-Object { $_ -match '\S' -and $_ -notmatch '^\s*#' } | ForEach-Object {
    $parts = $_ -split '=', 2
    if ($parts.Length -eq 2) {
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
    }
}

$LogDir = Join-Path $RepoRoot "sandbox"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "task-scheduler.log"

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting run_once()" | Out-File -Append -Encoding utf8 $LogFile
& uv run python -m src.wrapper.run --once *>> $LogFile
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Exit code: $LASTEXITCODE" | Out-File -Append -Encoding utf8 $LogFile
