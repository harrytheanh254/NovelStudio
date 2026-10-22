$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Repo = Join-Path $Root "vendor\Vietnamese-Long-Audio-TTS"
$VenvPython = Join-Path $Root "envs\audio-tts\Scripts\python.exe"
$Base = "https://raw.githubusercontent.com/harrytheanh254/Vietnamese-Long-Audio-TTS/main"

if (-not (Test-Path $VenvPython)) {
    throw "Khong tim thay Python audio: $VenvPython. Hay chay scripts\setup_audio.ps1 truoc."
}
New-Item -ItemType Directory -Force $Repo | Out-Null

Write-Host "Dang tai bo tao audio long-form cua Vietnamese-Long-Audio-TTS..."
Invoke-WebRequest -Uri "$Base/generate_audio.py" -OutFile (Join-Path $Repo "generate_audio.py")
Invoke-WebRequest -Uri "$Base/requirements.txt" -OutFile (Join-Path $Repo "requirements.txt")

$env:TEMP = Join-Path $Root "temp"
$env:TMP = Join-Path $Root "temp"
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

Write-Host "Dang cap nhat thu vien audio..."
& $VenvPython -m pip install --upgrade -r (Join-Path $Repo "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Cap nhat thu vien Vietnamese-Long-Audio-TTS that bai."
}

& $VenvPython -c "import importlib.metadata as m; print('Edge-TTS da cai:', m.version('edge-tts'))"
if ($LASTEXITCODE -ne 0) {
    throw "Khong kiem tra duoc phien ban Edge-TTS."
}
Write-Host "Da san sang: app se tao mot MP3 cho moi file TXT, khong can tu chia/tu ghep." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
