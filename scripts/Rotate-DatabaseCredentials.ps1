# Rotates MySQL users without deleting volumes. Secrets are sent through stdin only.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Env-Helpers.ps1')
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$envPath = Join-Path $projectRoot '.env'
$pendingPath = Join-Path $projectRoot '.env.rotation'
$values = Read-ProjectEnv $envPath
foreach ($key in @('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'MYSQL_USER')) {
    if (!$values.Contains($key) -or [string]::IsNullOrWhiteSpace($values[$key])) {
        throw 'An existing .env with the current database credentials is required.'
    }
}
if ($values['MYSQL_USER'] -notmatch '^[A-Za-z0-9_]+$' -or $values['MYSQL_USER'] -eq 'root') {
    throw 'MYSQL_USER must be a non-root application account using letters, digits or underscores.'
}
if (!(Test-Path -LiteralPath $pendingPath)) {
    Set-ProjectEnv $pendingPath ([ordered]@{
        MYSQL_PASSWORD = (New-ProjectPassword)
        MYSQL_ROOT_PASSWORD = (New-ProjectPassword)
    })
}
$pending = Read-ProjectEnv $pendingPath
foreach ($key in @('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD')) {
    if ($pending[$key] -notmatch '^[a-f0-9]{64}$') { throw 'Invalid pending credentials file.' }
}

function Invoke-DatabaseSql([string]$Password, [string]$Sql, [string]$User = 'root') {
    # Passwords are not process arguments or shell substitutions. Never echo mysql output on errors.
    $command = 'IFS= read -r MYSQL_PWD; export MYSQL_PWD; exec mysql --batch --skip-column-names --user=' + $User
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = ($Password + "`n" + $Sql + "`n") | & docker compose exec -T db sh -c $command 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'Database access failed; no credentials were printed.' }
        return $output
    } finally { $ErrorActionPreference = $previousPreference }
}

Push-Location $projectRoot
try {
    try {
        $accounts = @(Invoke-DatabaseSql $values['MYSQL_ROOT_PASSWORD'] (
            "SELECT User, Host FROM mysql.user WHERE User IN ('root', '" + $values['MYSQL_USER'] + "');"
        ))
    } catch {
        # Recovery if ALTER USER succeeded but a prior run stopped before updating local files.
        $accounts = @(Invoke-DatabaseSql $pending['MYSQL_ROOT_PASSWORD'] (
            "SELECT User, Host FROM mysql.user WHERE User IN ('root', '" + $values['MYSQL_USER'] + "');"
        ))
        $values['MYSQL_ROOT_PASSWORD'] = $pending['MYSQL_ROOT_PASSWORD']
    }
    $clauses = @()
    $foundApp = $false
    $foundRoot = $false
    foreach ($account in $accounts) {
        $parts = ([string]$account).Split("`t")
        if ($parts.Count -ne 2) { throw 'Unexpected MySQL account response.' }
        $user = $parts[0]
        $hostName = $parts[1].Replace("'", "''")
        if ($user -eq 'root') { $password = $pending['MYSQL_ROOT_PASSWORD']; $foundRoot = $true }
        elseif ($user -eq $values['MYSQL_USER']) { $password = $pending['MYSQL_PASSWORD']; $foundApp = $true }
        else { throw 'Unexpected database account.' }
        $clauses += "'$user'@'$hostName' IDENTIFIED BY '$password'"
    }
    if (!$foundApp -or !$foundRoot) { throw 'Expected root and application accounts were not found.' }
    # One atomic ALTER USER statement; NO_BACKSLASH_ESCAPES makes host quoting unambiguous.
    $sql = "SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES'; ALTER USER " + ($clauses -join ', ') + ';'
    $null = Invoke-DatabaseSql $values['MYSQL_ROOT_PASSWORD'] $sql
    $null = Invoke-DatabaseSql $pending['MYSQL_ROOT_PASSWORD'] 'SELECT 1;'
    $null = Invoke-DatabaseSql $pending['MYSQL_PASSWORD'] 'SELECT 1;' $values['MYSQL_USER']
    # Only replace active config after the new database credentials work.
    Set-ProjectEnv $envPath $pending
    foreach ($key in $pending.Keys) { $values[$key] = $pending[$key] }
    Sync-BackendEnv $projectRoot $values
    Remove-Item -LiteralPath $pendingPath
    Write-Output 'Database passwords rotated and local environment synchronized. Data was preserved.'
    Write-Output 'Run: docker compose up --build -d --force-recreate'
} catch {
    throw 'Rotation not finalized. Active .env was preserved; .env.rotation retains pending credentials. Start Docker and the existing db, then rerun this script. No volumes were deleted.'
} finally { Pop-Location }
