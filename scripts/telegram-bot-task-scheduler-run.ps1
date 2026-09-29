# Windows Task Scheduler entry point for the Aethon Telegram bot
# (src/telegram/bot.py). Unlike task-scheduler-run.ps1 (which runs
# run_once() once per night), this launches the bot's long-polling
# process (application.run_polling()) and keeps it running -- it's what
# actually answers /status, /chapter, /query etc. live. Without this
# running continuously, none of the interactive commands work, even
# though the command menu (setMyCommands) still shows up in the client.

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
$LogFile = Join-Path $LogDir "telegram-bot.log"

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting bot polling" | Out-File -Append -Encoding utf8 $LogFile
& uv run python -m src.telegram.bot *>> $LogFile
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Bot process exited, code: $LASTEXITCODE" | Out-File -Append -Encoding utf8 $LogFile
