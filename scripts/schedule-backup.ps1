param(
    [string]$Time = '03:00',
    [string]$BackupDirectory,
    [string]$CopyDirectory,
    [string]$Container = 'mudai_postgres'
)
$ErrorActionPreference = 'Stop'
if (-not $BackupDirectory) { $BackupDirectory = Join-Path $PSScriptRoot '../backups' }
$script = Join-Path $PSScriptRoot 'database.ps1'
foreach ($value in @($script, $BackupDirectory, $CopyDirectory, $Container)) {
    if ($value -match '["\r\n]') { throw 'Paths and container name cannot contain quotes or newlines.' }
}
$arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $script +
    '" -Action Backup -Container "' + $Container + '" -BackupDirectory "' +
    [IO.Path]::GetFullPath($BackupDirectory) + '"'
if ($CopyDirectory) { $arguments += ' -CopyDirectory "' + [IO.Path]::GetFullPath($CopyDirectory) + '"' }
$action = New-ScheduledTaskAction -Execute "$PSHOME\powershell.exe" -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($Time, 'HH:mm', $null))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
# Deliberately fail on an existing task so a custom schedule is not silently replaced.
Register-ScheduledTask -TaskName 'MuddAI-DatabaseBackup' -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description 'Nightly PostgreSQL backup; requires Docker Desktop and signed-in user.' | Out-Null
Write-Output "Registered MuddAI-DatabaseBackup at $Time local time. Docker Desktop must be running and the user signed in."
