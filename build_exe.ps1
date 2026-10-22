# Build the portable Windows distribution and ZIP archive.
param(
    [switch]$SkipInstall,
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "AURA Studio build" -ForegroundColor Yellow
python --version
if (-not $SkipInstall) {
    python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    python -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "dependency installation failed" }
}

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

if ($OneFile) {
    $env:AURA_ONEFILE = "1"
} else {
    Remove-Item Env:AURA_ONEFILE -ErrorAction SilentlyContinue
}

python -m PyInstaller --noconfirm --clean aura.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if ($OneFile) {
    Remove-Item Env:AURA_ONEFILE -ErrorAction SilentlyContinue
    $Target = "dist\AURA.exe"
} else {
    $Target = "dist\AURA\AURA.exe"
    Copy-Item README_RU.md dist\AURA\README_RU.md -Force
}

if (-not (Test-Path $Target)) {
    throw "Build failed: $Target not found"
}

$Version = (python -c "from core.config import APP_VERSION; print(APP_VERSION)").Trim()
$Zip = "dist\AURA-Studio-$Version-Windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
if ($OneFile) {
    Compress-Archive -Path $Target -DestinationPath $Zip
} else {
    Compress-Archive -Path "dist\AURA\*" -DestinationPath $Zip
}

$ApkSource = "mobile_android\app\build\outputs\apk\debug\app-debug.apk"
$ApkTarget = "dist\AURA-Mobile-$Version-debug.apk"
if (Test-Path $ApkSource) {
    Copy-Item $ApkSource $ApkTarget -Force
    Write-Host "APK:   $ApkTarget" -ForegroundColor Green
}

$Artifacts = @($Target, $Zip)
if (Test-Path $ApkTarget) { $Artifacts += $ApkTarget }
$Artifacts | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash.ToLower()
    "$hash  $(Split-Path -Leaf $_)"
} | Set-Content -Encoding ASCII -LiteralPath "dist\SHA256SUMS.txt"

Write-Host ""
Write-Host "Built: $Target" -ForegroundColor Green
Write-Host "ZIP:   $Zip" -ForegroundColor Green
Write-Host "Run $Target to start AURA Studio."
