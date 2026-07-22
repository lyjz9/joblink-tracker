param(
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& $Python -m pip install -r requirements-desktop.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
& $Python -m playwright install chromium --only-shell
& $Python -m PyInstaller --noconfirm --clean packaging\linc.spec

$Bundle = Join-Path $ProjectRoot "dist\Linc"
Copy-Item "templates\linc_tracker_template.xlsx" `
    (Join-Path $Bundle "Blank Linc Tracker.xlsx") -Force

$Archive = Join-Path $ProjectRoot "dist\Linc-v0.1.0-Windows.zip"
if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}
Compress-Archive -Path $Bundle -DestinationPath $Archive -CompressionLevel Optimal

Write-Host "Desktop beta ready: $Archive"
