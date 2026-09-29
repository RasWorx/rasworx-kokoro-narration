# Installs Kokoro narration into the folder this script lives in. Safe to run again.
#   setup.bat            full setup (GPU build of torch, CUDA 12.8)
#   setup.bat -Cpu       CPU-only torch (no NVIDIA GPU; slower)
#   setup.bat -NoShortcut
param([switch]$Cpu, [switch]$NoShortcut)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
Write-Host "Installing into: $root" -ForegroundColor Cyan

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Run($exe, $arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $exe $($arguments -join ' ')" }
}

Step 'Checking uv (the Python installer)'
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Run winget @('install', '--id', 'astral-sh.uv', '-e', '--accept-package-agreements', '--accept-source-agreements')
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
        $uv = Get-Command uv -ErrorAction SilentlyContinue
    }
    if (-not $uv) { throw 'uv is not installed. Install it from https://docs.astral.sh/uv/ and run setup.bat again.' }
}

Step 'Creating .venv with Python 3.12 (Kokoro does not support 3.13+)'
if (-not (Test-Path '.venv\Scripts\python.exe')) { Run uv @('venv', '--python', '3.12', '.venv') } else { Write-Host '.venv already exists' }
$py = Join-Path $root '.venv\Scripts\python.exe'

Step 'Installing torch'
$index = if ($Cpu) { 'https://download.pytorch.org/whl/cpu' } else { 'https://download.pytorch.org/whl/cu128' }
Run uv @('pip', 'install', '--python', $py, 'torch', '--index-url', $index)

Step 'Installing requirements.txt'
Run uv @('pip', 'install', '--python', $py, '-r', 'requirements.txt')

Step 'Creating folders'
foreach ($d in 'input', 'output') { New-Item -ItemType Directory -Force -Path $d | Out-Null }

Step 'Linking the Claude skills (.claude\skills)'
New-Item -ItemType Directory -Force -Path '.claude\skills' | Out-Null
foreach ($skill in 'kokoro-help', 'tts-output') {
    $link = ".claude\skills\$skill"
    $target = Join-Path $root ".agents\skills\$skill"
    if ((Test-Path $target) -and -not (Test-Path $link)) {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Host "linked $skill"
    }
}

if (-not $NoShortcut) {
    Step 'Creating the desktop shortcut'
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Kokoro narration.lnk'))
    $lnk.TargetPath = Join-Path $root 'ui.bat'
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = (Join-Path $root 'images\favicon.ico') + ',0'
    $lnk.WindowStyle = 7  # minimized, so the launcher console does not flash
    $lnk.Description = 'Kokoro narration: text to MP3, offline'
    $lnk.Save()
    Write-Host "Shortcut: $($lnk.FullName)"
}

Step 'Checking the install'
Run $py @('-c', 'import torch, kokoro; print(torch.__version__, torch.cuda.is_available())')
Write-Host "`nDone. Open the window from the desktop shortcut or ui.bat." -ForegroundColor Green
Write-Host 'The first run downloads the model (about 330 MB) into %USERPROFILE%\.cache\huggingface.'
