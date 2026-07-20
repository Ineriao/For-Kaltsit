param(
    [switch]$EnvironmentOnly
)

$ErrorActionPreference = 'Stop'

$repository = Resolve-Path (Join-Path $PSScriptRoot '..')
$backend = Join-Path $repository 'backend'
$environment = Join-Path $backend '.build-venv311'
$python = Join-Path $environment 'Scripts\python.exe'
$dist = Join-Path $backend 'dist-onefile-v10'
$work = Join-Path $backend 'build-pyinstaller-onefile-v10'

function Test-Python311([string]$candidate) {
    if (-not $candidate -or -not (Test-Path $candidate -PathType Leaf)) {
        return $false
    }
    & $candidate -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Find-Python311 {
    if (Test-Python311 $env:KALTSIT_PYTHON311) {
        return (Resolve-Path $env:KALTSIT_PYTHON311).Path
    }

    $registrations = & py -0p 2>$null
    foreach ($registration in $registrations) {
        if ($registration -match '([A-Za-z]:\\.*python\.exe)\s*$' -and (Test-Python311 $Matches[1])) {
            return (Resolve-Path $Matches[1]).Path
        }
    }
    return $null
}

if (-not (Test-Python311 $python)) {
    if (Test-Path $environment) {
        Remove-Item -LiteralPath $environment -Recurse -Force
    }
    $basePython = Find-Python311
    if (-not $basePython) {
        throw 'Python 3.11 was not found. Set KALTSIT_PYTHON311 to a valid python.exe.'
    }
    & $basePython -m venv $environment
    if ($LASTEXITCODE -ne 0 -or -not (Test-Python311 $python)) {
        throw 'Python 3.11 build environment could not be created.'
    }
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $python -m pip install -r (Join-Path $backend 'requirements.txt') 'pyinstaller==6.21.0'
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

if ($EnvironmentOnly) {
    Write-Host "Backend environment ready: $python"
    return
}

foreach ($directory in @($dist, $work)) {
    if (Test-Path $directory) {
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
}

& $python -m PyInstaller `
    --distpath $dist `
    --workpath $work `
    (Join-Path $backend 'kaltsit-backend.spec')
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }
