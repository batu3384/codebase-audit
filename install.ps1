#Requires -Version 5.1
# Install codebase-audit into %USERPROFILE%\.agents\skills, then link Cursor / Claude / Antigravity.
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$Agents = Join-Path $env:USERPROFILE ".agents\skills\codebase-audit"

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

if (Test-Path $Agents) {
    Remove-Item -Recurse -Force $Agents
}
New-Item -ItemType Directory -Force -Path $Agents | Out-Null
Get-ChildItem -Path $RepoRoot -Force | Where-Object { $_.Name -ne ".git" } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $Agents -Recurse -Force
}

$py = Get-PythonLauncher
& $py.Name @($py.Args + @((Join-Path $Agents "scripts\install_links.py"), "--agents", $Agents))
& $py.Name @($py.Args + @((Join-Path $Agents "scripts\self-check.py")))

Write-Host "Installed: $Agents"
Write-Host "Codex reads %USERPROFILE%\.agents\skills (no extra link)."
Write-Host "Skipped on purpose: .gemini\skills (Gemini CLI), .codex\skills (catalog)."
Write-Host "On Windows, ~ in docs means %USERPROFILE%."
