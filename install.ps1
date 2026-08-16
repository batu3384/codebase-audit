#Requires -Version 5.1
# Install codebase-audit into %USERPROFILE%\.agents\skills and junction %USERPROFILE%\.cursor\skills (Windows).
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$Agents = Join-Path $env:USERPROFILE ".agents\skills\codebase-audit"
$CursorSkills = Join-Path $env:USERPROFILE ".cursor\skills"
$CursorLink = Join-Path $CursorSkills "codebase-audit"

function Get-PythonLauncher {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Name = "python"; Args = @() }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Name = "py"; Args = @("-3") }
    }
    throw "Python 3 not found. Install from https://www.python.org/downloads/ and retry."
}

New-Item -ItemType Directory -Force -Path (Split-Path $Agents) | Out-Null
New-Item -ItemType Directory -Force -Path $CursorSkills | Out-Null

if (Test-Path $Agents) {
    Remove-Item -Recurse -Force $Agents
}
New-Item -ItemType Directory -Force -Path $Agents | Out-Null
Get-ChildItem -Path $RepoRoot -Force | Where-Object { $_.Name -ne ".git" } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $Agents -Recurse -Force
}

if (Test-Path $CursorLink) {
    Remove-Item -Recurse -Force $CursorLink
}
cmd /c "mklink /J `"$CursorLink`" `"$Agents`"" | Out-Null

$py = Get-PythonLauncher
$selfCheck = Join-Path $Agents "scripts\self-check.py"
& $py.Name @($py.Args + @($selfCheck))

Write-Host "Installed: $Agents"
Write-Host "Cursor:    $CursorLink"
