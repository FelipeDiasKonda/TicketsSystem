# Creates development credentials locally. Does not change an existing database password.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Env-Helpers.ps1')
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$envPath = Join-Path $projectRoot '.env'
if (!(Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envPath
}
$values = Read-ProjectEnv $envPath
$updates = [ordered]@{}
foreach ($key in @('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD')) {
    if (!$values.Contains($key) -or [string]::IsNullOrWhiteSpace($values[$key])) {
        $updates[$key] = New-ProjectPassword
        $values[$key] = $updates[$key]
    }
}
if ($updates.Count -gt 0) { Set-ProjectEnv $envPath $updates }
Sync-BackendEnv $projectRoot $values
Write-Output 'Local environment configured. Existing non-empty passwords were preserved.'
Write-Output 'For an existing database, use Rotate-DatabaseCredentials.ps1 to rotate passwords.'
