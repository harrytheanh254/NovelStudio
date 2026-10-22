$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = "D:\Python312\python.exe"
$Venv = Join-Path $Root "envs\audio-tts"
$Cache = Join-Path $Root "cache\pip"
$Temp = Join-Path $Root "temp"
$Repo = Join-Path $Root "vendor\Vietnamese-Long-Audio-TTS"

if (-not (Test-Path $Python)) { throw "Khong tim thay Python 3.12: $Python" }
if (-not (Test-Path (Join-Path $Repo "requirements.txt"))) {
    Write-Host "Can clone repo audio vao: $Repo" -ForegroundColor Red
    Read-Host "Nhan Enter de thoat"
    exit 1
}
New-Item -ItemType Directory -Force -Path $Cache, $Temp | Out-Null
$env:PIP_CACHE_DIR = $Cache; $env:TEMP = $Temp; $env:TMP = $Temp
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) { & $Python -m venv $Venv }
$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install -r (Join-Path $Repo "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Cai thu vien audio that bai." }
& $VenvPython -m pip install imageio-ffmpeg
if ($LASTEXITCODE -ne 0) { throw "Cai cong cu ghep MP3 that bai." }
Write-Host "Da cai xong thu vien audio va cong cu ghep cac phan thanh mot file MP3." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
