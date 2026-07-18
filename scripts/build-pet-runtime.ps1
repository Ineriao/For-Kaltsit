$ErrorActionPreference = 'Stop'

$repository = Resolve-Path (Join-Path $PSScriptRoot '..')
$petProject = Join-Path $repository 'kaltsit-pet'
$toolDirectory = Join-Path $repository '.build-tools'
$runtime = Join-Path $petProject 'build\runtime'
$configuredJdk = $env:KALTSIT_JDK17

if (Test-Path $runtime) {
    throw "Java runtime output already exists: $runtime"
}

if ($configuredJdk -and (Test-Path (Join-Path $configuredJdk 'bin\jlink.exe'))) {
    $jdk = Resolve-Path $configuredJdk
} else {
    $jdk = Get-ChildItem `
        $toolDirectory, `
        (Join-Path $env:ProgramFiles 'Microsoft'), `
        (Join-Path $env:ProgramFiles 'Eclipse Adoptium') `
        -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName 'bin\jlink.exe') } |
        Where-Object { (& (Join-Path $_.FullName 'bin\java.exe') -version 2>&1) -match 'version "17\.' } |
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
        Where-Object { Test-Path (Join-Path $_.FullName 'bin\jlink.exe') } |
        Where-Object { (& (Join-Path $_.FullName 'bin\java.exe') -version 2>&1) -match 'version "17\.' } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $jdk) {
    throw 'Java 17 JDK was not found.'
}

$env:JAVA_HOME = $jdk
$env:Path = "$(Join-Path $jdk 'bin');$env:Path"

& (Join-Path $petProject 'gradlew.bat') -p $petProject jar
& (Join-Path $jdk 'bin\jlink.exe') `
    --add-modules 'java.base,java.desktop,java.logging,java.management,java.naming,jdk.unsupported,jdk.crypto.ec' `
    --strip-debug `
    --no-header-files `
    --no-man-pages `
    --compress=2 `
    --output $runtime
