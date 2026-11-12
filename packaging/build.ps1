# Builds dist\FFHelper-Setup-<version>.exe. Run on Windows:
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Needs uv and Inno Setup 6 (winget install JRSoftware.InnoSetup).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE) { throw "$Name failed (exit code $LASTEXITCODE)" }
}

Invoke-Step "Install dependencies" { uv sync --group build }
Invoke-Step "Run tests" { uv run pytest -q }
Invoke-Step "Bundle the app" { uv run pyinstaller packaging\ffhelper.spec --noconfirm --clean }

$version = (uv run python -c "import ffhelper; print(ffhelper.__version__)").Trim()
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $iscc = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup" }
Invoke-Step "Build the installer" { & $iscc "/DAppVersion=$version" packaging\installer.iss }

Write-Host "Done: dist\FFHelper-Setup-$version.exe"
