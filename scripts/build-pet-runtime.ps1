$ErrorActionPreference = 'Stop'

$repository = Resolve-Path (Join-Path $PSScriptRoot '..')
$petProject = Join-Path $repository 'kaltsit-pet'
$toolDirectory = Join-Path $repository '.build-tools'
$runtime = Join-Path $petProject 'build\runtime'
$configuredJdk = $env:KALTSIT_JDK17

function Test-Jdk17([string]$candidate) {
    if (-not $candidate) { return $false }
    $java = Join-Path $candidate 'bin\java.exe'
    $javac = Join-Path $candidate 'bin\javac.exe'
    $jlink = Join-Path $candidate 'bin\jlink.exe'
    if (-not (Test-Path $java) -or -not (Test-Path $javac) -or -not (Test-Path $jlink)) {
        return $false
    }
    return ((& $java --version) -match '^openjdk 17\.')
}

if (Test-Jdk17 $configuredJdk) {
    $jdk = Resolve-Path $configuredJdk
} else {
    $jdk = Get-ChildItem `
        $toolDirectory, `
        (Join-Path $env:ProgramFiles 'Microsoft'), `
        (Join-Path $env:ProgramFiles 'Eclipse Adoptium') `
        -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Jdk17 $_.FullName } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $jdk) {
    New-Item -ItemType Directory -Force -Path $toolDirectory | Out-Null
    $archive = Join-Path $toolDirectory 'temurin-jdk17.zip'
    if (-not (Test-Path $archive)) {
        Invoke-WebRequest `
            -Uri 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' `
            -OutFile $archive
    }
    Expand-Archive -Path $archive -DestinationPath $toolDirectory
    $jdk = Get-ChildItem $toolDirectory -Directory |
        Where-Object { Test-Jdk17 $_.FullName } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $jdk) {
    throw 'Java 17 JDK was not found.'
}

$env:JAVA_HOME = $jdk
$env:Path = "$(Join-Path $jdk 'bin');$env:Path"

if (Test-Path $runtime) {
    Remove-Item -LiteralPath $runtime -Recurse -Force
}

& (Join-Path $petProject 'gradlew.bat') -p $petProject jar
if ($LASTEXITCODE -ne 0) { throw 'Desktop pet build failed.' }
& (Join-Path $jdk 'bin\jlink.exe') `
    --add-modules 'java.base,java.desktop,java.logging,java.management,java.naming,jdk.unsupported,jdk.crypto.ec' `
    --strip-debug `
    --no-header-files `
    --no-man-pages `
    --compress=2 `
    --output $runtime
if ($LASTEXITCODE -ne 0) { throw 'Java runtime packaging failed.' }
