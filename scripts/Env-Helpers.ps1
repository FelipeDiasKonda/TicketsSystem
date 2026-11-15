Set-StrictMode -Version Latest

function Read-ProjectEnv([string]$Path) {
    $values = [ordered]@{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in [IO.File]::ReadAllLines($Path)) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
                $value = $Matches[2].Trim()
                if ($value.Length -ge 2 -and (
                    ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                    ($value.StartsWith("'") -and $value.EndsWith("'"))
                )) { $value = $value.Substring(1, $value.Length - 2) }
                $values[$Matches[1]] = $value
            }
        }
    }
    return $values
}

function Set-ProjectEnv([string]$Path, [System.Collections.IDictionary]$Values) {
    $lines = if (Test-Path -LiteralPath $Path) { [IO.File]::ReadAllLines($Path) } else { @() }
    $remaining = [ordered]@{}
    foreach ($key in $Values.Keys) { $remaining[$key] = $Values[$key] }
    $output = foreach ($line in $lines) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=' -and $remaining.Contains($Matches[1])) {
            $key = $Matches[1]
            "$key=$($remaining[$key])"
            $remaining.Remove($key)
        } else { $line }
    }
    $output = @($output) + @(foreach ($key in $remaining.Keys) { "$key=$($remaining[$key])" })
    [IO.File]::WriteAllText($Path, ($output -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
}

function New-ProjectPassword {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

function Sync-BackendEnv([string]$ProjectRoot, [System.Collections.IDictionary]$Values) {
    $path = Join-Path $ProjectRoot 'backend/.env'
    if (!(Test-Path -LiteralPath $path)) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot 'backend/.env.example') -Destination $path
    }
    Set-ProjectEnv $path ([ordered]@{
        DATABASE_HOST = '127.0.0.1'
        DATABASE_PORT = $Values['MYSQL_PORT']
        DATABASE_NAME = $Values['MYSQL_DATABASE']
        DATABASE_USER = $Values['MYSQL_USER']
        DATABASE_PASSWORD = $Values['MYSQL_PASSWORD']
    })
}
