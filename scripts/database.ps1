param(
    [Parameter(Mandatory)][ValidateSet('Backup', 'Restore', 'Verify')][string]$Action,
    [string]$Container = 'mudai_postgres',
    [string]$BackupDirectory,
    [string]$Archive,
    [ValidatePattern('^[a-z][a-z0-9_]{0,62}$')][string]$TargetDatabase,
    [string]$CopyDirectory,
    [switch]$ConfirmRestore
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $BackupDirectory) { $BackupDirectory = Join-Path $PSScriptRoot '../backups' }

function Invoke-Docker {
    param([string[]]$DockerArgs)
    $result = & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed (exit $LASTEXITCODE)." }
    return $result
}

function Assert-Archive {
    param([string]$Path)
    if (-not $Path) { throw 'Specify -Archive.' }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $expected = (Get-Content -LiteralPath "$resolved.sha256" -Raw).Trim()
    if ($expected -notmatch '^[a-fA-F0-9]{64}$' -or
        (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash -ne $expected) {
        throw 'Backup checksum mismatch.'
    }
    return $resolved
}

function Remove-OldBackups {
    param([string]$Directory)
    # Keep the latest backup from seven distinct UTC days and four ISO-style weeks.
    $files = @(Get-ChildItem -LiteralPath $Directory -File -Filter 'muddb-*.dump' |
        Where-Object { $_.Name -match '^muddb-\d{8}T\d{9}Z-[a-f0-9]{8}\.dump$' -and
            (Test-Path -LiteralPath ($_.FullName + '.sha256')) } |
        Sort-Object Name -Descending)
    $daily = @{}; $weekly = @{}; $keep = @{}
    foreach ($file in $files) {
        $date = [datetime]::ParseExact($file.Name.Substring(6, 8), 'yyyyMMdd',
            [Globalization.CultureInfo]::InvariantCulture)
        $day = $date.ToString('yyyy-MM-dd')
        $week = $date.AddDays(-(([int]$date.DayOfWeek + 6) % 7)).ToString('yyyy-MM-dd')
        if (-not $daily.ContainsKey($day) -and $daily.Count -lt 7) {
            $daily[$day] = $true; $keep[$file.Name] = $true
        }
        if (-not $weekly.ContainsKey($week) -and $weekly.Count -lt 4) {
            $weekly[$week] = $true; $keep[$file.Name] = $true
        }
    }
    foreach ($file in $files) {
        if (-not $keep.ContainsKey($file.Name)) {
            Remove-Item -LiteralPath $file.FullName
            Remove-Item -LiteralPath ($file.FullName + '.sha256')
        }
    }
}

$token = [guid]::NewGuid().ToString('N')
$remote = "/tmp/mudai-backup-$token.dump"
$lock = $null
$temporary = $null
$verifyContainer = $null
try {
    if ($Action -eq 'Backup') {
        $directory = [IO.Path]::GetFullPath($BackupDirectory)
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        $lock = [IO.File]::Open((Join-Path $directory '.backup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        $name = 'muddb-' + [datetime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + $token.Substring(0, 8) + '.dump'
        $destination = Join-Path $directory $name
        $temporary = "$destination.partial"
        $dbUser = (Invoke-Docker @('exec', $Container, 'printenv', 'POSTGRES_USER')).Trim()
        $dbName = (Invoke-Docker @('exec', $Container, 'printenv', 'POSTGRES_DB')).Trim()
        Invoke-Docker @('exec', $Container, 'pg_dump', '-U', $dbUser, '-d', $dbName, '-Fc', '-f', $remote) | Out-Null
        Invoke-Docker @('exec', $Container, 'pg_restore', '--list', $remote) | Out-Null
        Invoke-Docker @('cp', "${Container}:$remote", $temporary) | Out-Null
        $hash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash
        Move-Item -LiteralPath $temporary -Destination $destination
        Set-Content -LiteralPath "$destination.sha256" -Value $hash -Encoding ASCII
        if ($CopyDirectory) {
            $copyRoot = [IO.Path]::GetFullPath($CopyDirectory)
            if ($copyRoot.TrimEnd('\', '/') -eq $directory.TrimEnd('\', '/')) {
                throw 'CopyDirectory must differ from BackupDirectory.'
            }
            New-Item -ItemType Directory -Path $copyRoot -Force | Out-Null
            $copyPath = Join-Path $copyRoot $name
            Copy-Item -LiteralPath $destination -Destination "$copyPath.partial"
            if ((Get-FileHash -LiteralPath "$copyPath.partial").Hash -ne $hash) { throw 'Second copy checksum mismatch.' }
            Move-Item -LiteralPath "$copyPath.partial" -Destination $copyPath
            Copy-Item -LiteralPath "$destination.sha256" -Destination "$copyPath.sha256"
            Remove-OldBackups $copyRoot
        }
        Remove-OldBackups $directory
        Write-Output "Backup created: $destination"
    } else {
        $source = Assert-Archive $Archive
        if ($Action -eq 'Verify') {
            $verifyContainer = "mudai-backup-check-$token"
            Invoke-Docker @('run', '-d', '--name', $verifyContainer, '--network', 'none',
                '--tmpfs', '/var/lib/postgresql/data', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
                'postgres:16-alpine') | Out-Null
            $Container = $verifyContainer
            $ready = $false
            for ($attempt = 0; $attempt -lt 30; $attempt++) {
                & docker exec $Container pg_isready -h 127.0.0.1 -U postgres *> $null
                if ($LASTEXITCODE -eq 0) { $ready = $true; break }
                Start-Sleep -Seconds 1
            }
            if (-not $ready) { throw 'Verification database did not become ready.' }
            $TargetDatabase = 'backup_check'
            $dbUser = 'postgres'
        } elseif (-not $TargetDatabase -or -not $ConfirmRestore) {
            throw 'Restore requires -TargetDatabase <new_database> and -ConfirmRestore. Existing databases are never overwritten.'
        } else {
            $dbUser = (Invoke-Docker @('exec', $Container, 'printenv', 'POSTGRES_USER')).Trim()
        }
        Invoke-Docker @('cp', $source, "${Container}:$remote") | Out-Null
        Invoke-Docker @('exec', $Container, 'pg_restore', '--list', $remote) | Out-Null
        # createdb fails if the target exists. Never drop a database automatically.
        Invoke-Docker @('exec', $Container, 'createdb', '-U', $dbUser, '--', $TargetDatabase) | Out-Null
        Invoke-Docker @('exec', $Container, 'pg_restore', '-U', $dbUser, '-d', $TargetDatabase,
            '--no-owner', '--no-privileges', '--exit-on-error', '--single-transaction', $remote) | Out-Null
        # Return only aggregate counts, never player data or credentials.
        Invoke-Docker @('exec', $Container, 'psql', '-X', '-U', $dbUser, '-d', $TargetDatabase,
            '-v', 'ON_ERROR_STOP=1', '-c',
            'SELECT version_num FROM alembic_version; SELECT count(*) AS rooms FROM rooms; SELECT count(*) AS players FROM players; SELECT count(*) AS npc_memories FROM npc_memories;')
        Write-Output "$Action succeeded: $TargetDatabase"
    }
} finally {
    if ($verifyContainer) {
        & docker rm -f $verifyContainer | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning "Could not remove verification container $verifyContainer" }
    } else {
        & docker exec $Container rm -f $remote | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Could not remove temporary archive from database container.' }
    }
    if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary }
    if ($lock) { $lock.Dispose() }
}
