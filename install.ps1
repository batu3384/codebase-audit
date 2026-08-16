#Requires -Version 5.1
# Install codebase-audit into %USERPROFILE%\.agents\skills, then link Cursor / Claude / Antigravity.
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot

function Get-PythonLauncher {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += @{ Name = "py"; Args = @("-3") }
    }
    if (Get-Command python3 -ErrorAction SilentlyContinue) {
        $candidates += @{ Name = "python3"; Args = @() }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += @{ Name = "python"; Args = @() }
    }
    foreach ($c in $candidates) {
        & $c.Name @($c.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"))
        if ($LASTEXITCODE -eq 0) {
            return $c
        }
    }
    throw "Python 3.10+ not found. Install from https://www.python.org/downloads/ and retry."
}

$py = Get-PythonLauncher
$installArgs = @((Join-Path $RepoRoot "scripts\install.py"), "--repo", $RepoRoot)
if ($env:AGENTS_DIR) {
    $installArgs += @("--agents-dir", $env:AGENTS_DIR)
}
& $py.Name @($py.Args + $installArgs)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
