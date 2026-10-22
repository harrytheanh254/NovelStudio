$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Repo = Join-Path $Root "vendor\Vietnamese-Long-Audio-TTS"
$VenvPython = Join-Path $Root "envs\audio-tts\Scripts\python.exe"
$AudioRepo = $env:NOVELSTUDIO_GITHUB_AUDIO_REPO
if ([string]::IsNullOrWhiteSpace($AudioRepo)) {
    $AudioRepo = "harrytheanh254/Vietnamese-Long-Audio-TTS"
}
$Base = "https://raw.githubusercontent.com/$AudioRepo/main"

if (-not (Test-Path $VenvPython)) {
    throw "Khong tim thay Python audio: $VenvPython. Hay chay scripts\setup_audio.ps1 truoc."
}
New-Item -ItemType Directory -Force $Repo | Out-Null

$GeneratorPath = Join-Path $Repo "generate_audio.py"
$RequirementsPath = Join-Path $Repo "requirements.txt"
$GhCommand = Get-Command gh -ErrorAction SilentlyContinue
$GhAuthenticated = $false
if ($GhCommand) {
    & gh auth status --hostname github.com *> $null
    $GhAuthenticated = ($LASTEXITCODE -eq 0)
}

Write-Host "Dang tai bo tao audio tu $AudioRepo..."
if ($GhAuthenticated) {
    # Use the authenticated Contents API so this updater also works after the repo is Private.
    $GeneratorBase64 = & gh api "repos/$AudioRepo/contents/generate_audio.py?ref=main" --jq .content
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($GeneratorBase64 -join ""))) {
        throw "Khong tai duoc generate_audio.py qua GitHub CLI."
    }
    $RequirementsBase64 = & gh api "repos/$AudioRepo/contents/requirements.txt?ref=main" --jq .content
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($RequirementsBase64 -join ""))) {
        throw "Khong tai duoc requirements.txt qua GitHub CLI."
    }
    try {
        $GeneratorEncoded = (($GeneratorBase64 -join "") -replace "\s", "")
        $RequirementsEncoded = (($RequirementsBase64 -join "") -replace "\s", "")
        [System.IO.File]::WriteAllBytes($GeneratorPath, [Convert]::FromBase64String($GeneratorEncoded))
        [System.IO.File]::WriteAllBytes($RequirementsPath, [Convert]::FromBase64String($RequirementsEncoded))
    } catch {
        throw "Khong giai ma duoc file tai tu GitHub API: $($_.Exception.Message)"
    }
} else {
    # Anonymous raw download remains available for a public repository.
    try {
        Invoke-WebRequest -Uri "$Base/generate_audio.py" -OutFile $GeneratorPath
        Invoke-WebRequest -Uri "$Base/requirements.txt" -OutFile $RequirementsPath
    } catch {
        throw "Khong tai duoc bo tao audio tu $AudioRepo. Neu repository Private, hay cai GitHub CLI va chay 'gh auth login' truoc."
    }
}

$env:TEMP = Join-Path $Root "temp"
$env:TMP = Join-Path $Root "temp"
New-Item -ItemType Directory -Force $env:TEMP | Out-Null

Write-Host "Dang cap nhat thu vien audio..."
& $VenvPython -m pip install --upgrade -r $RequirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Cap nhat thu vien Vietnamese-Long-Audio-TTS that bai."
}

& $VenvPython -c "import importlib.metadata as m; print('Edge-TTS da cai:', m.version('edge-tts'))"
if ($LASTEXITCODE -ne 0) {
    throw "Khong kiem tra duoc phien ban Edge-TTS."
}
Write-Host "Da san sang: app se tao mot MP3 cho moi file TXT, khong can tu chia/tu ghep." -ForegroundColor Green
Read-Host "Nhan Enter de dong"
