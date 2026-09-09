$ErrorActionPreference = 'Stop'
$container = 'mudai-backup-test-' + [guid]::NewGuid().ToString('N')
$directory = Join-Path ([IO.Path]::GetTempPath()) $container
$script = Join-Path $PSScriptRoot 'database.ps1'
function Docker-Check {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Docker test setup/check failed.' }
}
function Assert-Fails {
    param([scriptblock]$Operation, [string]$Expected)
    try { & $Operation } catch {
        if ($_.Exception.Message -notlike "*$Expected*") { throw }
        return
    }
    throw "Expected failure: $Expected"
}
try {
    New-Item -ItemType Directory -Path $directory | Out-Null
    Docker-Check @('run', '-d', '--name', $container, '--network', 'none',
        '--tmpfs', '/var/lib/postgresql/data', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
        '-e', 'POSTGRES_USER=fixture', '-e', 'POSTGRES_DB=fixture', 'postgres:16-alpine') | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        & docker exec $container pg_isready -h 127.0.0.1 -U fixture *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Fixture database did not become ready.' }
    Docker-Check @('exec', $container, 'psql', '-U', 'fixture', '-v', 'ON_ERROR_STOP=1', '-c',
        "CREATE TABLE rooms(id text PRIMARY KEY); INSERT INTO rooms VALUES ('inn'); CREATE TABLE players(id text PRIMARY KEY); CREATE TABLE npc_memories(id text); CREATE TABLE alembic_version(version_num text); INSERT INTO alembic_version VALUES ('fixture');") | Out-Null
    $copy = Join-Path $directory 'second-copy'
    & $script -Action Backup -Container $container -BackupDirectory $directory -CopyDirectory $copy
    $archive = (Get-ChildItem -LiteralPath $directory -Filter '*.dump')[0].FullName
    & $script -Action Verify -Archive $archive
    & $script -Action Restore -Container $container -Archive $archive -TargetDatabase recovered -ConfirmRestore
    $room = Docker-Check @('exec', $container, 'psql', '-U', 'fixture', '-d', 'recovered', '-Atc', 'SELECT id FROM rooms')
    if ($room -ne 'inn') { throw 'Restored fixture data differs.' }
    Assert-Fails { & $script -Action Restore -Container $container -Archive $archive -TargetDatabase recovered -ConfirmRestore } 'Docker operation failed'
    Assert-Fails { & $script -Action Restore -Container $container -Archive $archive -TargetDatabase missing_confirmation } 'requires'
    Add-Content -LiteralPath $archive -Value 'corruption'
    Assert-Fails { & $script -Action Restore -Container $container -Archive $archive -TargetDatabase corrupt -ConfirmRestore } 'checksum mismatch'
    $copyArchive = Join-Path $copy ([IO.Path]::GetFileName($archive))
    if ((Get-FileHash -LiteralPath $copyArchive).Hash -ne (Get-Content -LiteralPath "$copyArchive.sha256").Trim()) {
        throw 'Independent copy is invalid.'
    }
    # Exercise retention with synthetic archives in the isolated test directory.
    for ($day = 1; $day -le 45; $day++) {
        $name = 'muddb-' + [datetime]::UtcNow.AddDays(-$day).ToString('yyyyMMddTHHmmssfffZ') + '-12345678.dump'
        Set-Content -LiteralPath (Join-Path $directory $name) -Value 'fixture'
        Set-Content -LiteralPath (Join-Path $directory "$name.sha256") -Value 'fixture'
    }
    Set-Content -LiteralPath (Join-Path $directory 'unrelated.txt') -Value 'preserve'
    & $script -Action Backup -Container $container -BackupDirectory $directory
    $remaining = @(Get-ChildItem -LiteralPath $directory -Filter '*.dump')
    if ($remaining.Count -lt 7 -or $remaining.Count -gt 11) { throw 'Unexpected retention count.' }
    if (-not (Test-Path -LiteralPath (Join-Path $directory 'unrelated.txt'))) { throw 'Retention removed unrelated data.' }
    Write-Output 'PASS: backup, second copy, isolated verification, restore contents, existing-target refusal, confirmation, checksum, retention.'
} finally {
    & docker rm -f $container | Out-Null
    $resolved = [IO.Path]::GetFullPath($directory)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path.' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
