$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = "D:\Python312\python.exe"
$Venv = Join-Path $Root "envs\translation"
$Cache = Join-Path $Root "cache\pip"
$Temp = Join-Path $Root "temp"

if (-not (Test-Path $Python)) {
    Write-Host "Khong tim thay Python 3.12 tai $Python" -ForegroundColor Red
    Write-Host "Hay sua bien Python trong file setup_translation.ps1 cho dung duong dan Python 3.12 cua ban."
    Read-Host "Nhan Enter de thoat"
    exit 1
}
New-Item -ItemType Directory -Force -Path $Cache, $Temp, (Join-Path $Root "models\huggingface") | Out-Null
$env:PIP_CACHE_DIR = $Cache
$env:TEMP = $Temp
$env:TMP = $Temp
$env:HF_HOME = Join-Path $Root "models\huggingface"

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    & $Python -m venv $Venv
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Khong nang cap duoc pip." }
& $VenvPython -m pip install -r (Join-Path $Root "requirements-translation.txt")
if ($LASTEXITCODE -ne 0) { throw "Khong cai duoc thu vien dich." }
Write-Host "Da cai xong thu vien dich. Mo app va bam BAT DAU DICH de tai mo hinh lan dau." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
