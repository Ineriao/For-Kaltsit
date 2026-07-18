$ErrorActionPreference = 'Stop'

$repository = Resolve-Path (Join-Path $PSScriptRoot '..')
$backend = Join-Path $repository 'backend'
$environment = Join-Path $backend '.build-venv311'
$python = Join-Path $environment 'Scripts\python.exe'
$output = Join-Path $backend 'dist-onefile-v6\kaltsit-backend.exe'

if (Test-Path $output) {
    throw "Backend output already exists: $output"
}

if (-not (Test-Path $python)) {
    py -3.11 -m venv $environment
}

& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $backend 'requirements.txt') 'pyinstaller==6.21.0'
& $python -m PyInstaller `
    --distpath (Join-Path $backend 'dist-onefile-v6') `
    --workpath (Join-Path $backend 'build-pyinstaller-onefile-v6') `
    (Join-Path $backend 'kaltsit-backend.spec')
