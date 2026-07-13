param(
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& $Python -m pip install -r requirements-desktop.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
& $Python -m playwright install chromium --only-shell
& $Python -m PyInstaller --noconfirm --clean packaging\joblink_tracker.spec

$Bundle = Join-Path $ProjectRoot "dist\JobLink Tracker"
Copy-Item "templates\joblink_tracker_template.xlsx" `
    (Join-Path $Bundle "Blank JobLink Tracker.xlsx") -Force

$Archive = Join-Path $ProjectRoot "dist\JobLink-Tracker-Windows.zip"
if (Test-Path $Archive) {
    Remove-Item $Archive -Force
}
Compress-Archive -Path $Bundle -DestinationPath $Archive -CompressionLevel Optimal

Write-Host "Desktop beta ready: $Archive"
