param(
    [switch]$IncludeMobile,
    [switch]$ConfigureCodex
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

function Invoke-Python312 {
    param([string[]]$Arguments)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 @Arguments
        return
    }

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python 3.12 was not found. Install Python 3.12, then run this script again."
    }

    $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($version -ne "3.12") {
        throw "The available 'python' is $version. Python 3.12 is required for the optional mobile MCP."
    }
    & python @Arguments
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating project-local Python environment..."
    Invoke-Python312 -Arguments @("-m", "venv", $venvPath)
}

Write-Host "Installing core dependencies..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")

if ($IncludeMobile) {
    Write-Host "Installing optional Android mobile MCP from bundled source..."
    & $venvPython -m pip install -e (Join-Path $projectRoot "third_party\mobile-use-mcp")
}

& $venvPython (Join-Path $projectRoot "scripts\create_local_skeleton.py")
& $venvPython -c "import yaml; print('CORE_IMPORT_OK')"

if ($ConfigureCodex) {
    if (-not $IncludeMobile) {
        throw "-ConfigureCodex requires -IncludeMobile."
    }
    & $venvPython (Join-Path $projectRoot "scripts\configure_mobile_mcp.py")
}

Write-Host "BOOTSTRAP_OK"
Write-Host "Next: open the project in Codex and follow START_HERE.md."
if ($ConfigureCodex) {
    Write-Host "Restart Codex, then verify the mobile-use MCP connection."
}

