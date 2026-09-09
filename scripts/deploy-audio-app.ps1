[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$AdbPath = "$env:LOCALAPPDATA/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe",
    [string]$RemoteApp = "/home/arduino/ArduinoApps/audio-test"
)

$ErrorActionPreference = "Stop"
$expectedRoot = "D:/Repository/AMM/SylvaEchoLens/SylvaEchoLens"
$expectedOrigin = "https://github.com/AM275-pilot/SylvaEchoLens.git"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path.Replace("\", "/")

if ($root -ne $expectedRoot) { throw "Refusing deployment from unexpected root: $root" }
if ($RemoteApp -ne "/home/arduino/ArduinoApps/audio-test") {
    throw "Refusing unexpected remote app path: $RemoteApp"
}
if (-not (Test-Path -LiteralPath $AdbPath)) { throw "ADB not found: $AdbPath" }
$origin = (git -C $root remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $origin -ne $expectedOrigin) {
    throw "Unexpected Git origin: $origin"
}

function Invoke-Adb([string[]]$Arguments) {
    & $AdbPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ADB failed: $($Arguments -join ' ')"
    }
}

Invoke-Adb @("get-state")
if ($WhatIfPreference) {
    [void]$PSCmdlet.ShouldProcess(
        $RemoteApp,
        "snapshot, stop, deploy matching receiver sources, and restart"
    )
    return
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$rollback = Join-Path $root ".codex-build/rollback/$stamp-before-app-deploy"
$pythonRollback = Join-Path $rollback "python"
New-Item -ItemType Directory -Force $pythonRollback | Out-Null

Invoke-Adb @("pull", "$RemoteApp/app.yaml", (Join-Path $rollback "app.yaml"))
$requirementsExisted = $false
& $AdbPath shell "test -f $RemoteApp/python/requirements.txt"
if ($LASTEXITCODE -eq 0) {
    $requirementsExisted = $true
    Invoke-Adb @(
        "pull", "$RemoteApp/python/requirements.txt",
        (Join-Path $pythonRollback "requirements.txt")
    )
}
foreach ($name in @("main.py", "event_receiver.py")) {
    Invoke-Adb @("pull", "$RemoteApp/python/$name", (Join-Path $pythonRollback $name))
}
$classificationExisted = $false
& $AdbPath shell "test -f $RemoteApp/python/classification.py"
if ($LASTEXITCODE -eq 0) {
    $classificationExisted = $true
    Invoke-Adb @(
        "pull", "$RemoteApp/python/classification.py",
        (Join-Path $pythonRollback "classification.py")
    )
}

if (-not $PSCmdlet.ShouldProcess($RemoteApp, "stop, deploy matching receiver sources, and restart")) {
    Write-Output "Rollback snapshot: $rollback"
    return
}

$stopped = $false
try {
    Invoke-Adb @("shell", "arduino-app-cli app stop $RemoteApp")
    $stopped = $true
    Invoke-Adb @("push", (Join-Path $root "app_audio_test/app.yaml"), "$RemoteApp/app.yaml")
    foreach ($name in @("main.py", "event_receiver.py", "classification.py", "requirements.txt")) {
        Invoke-Adb @("push", (Join-Path $root "app_audio_test/python/$name"), "$RemoteApp/python/$name")
    }
    Invoke-Adb @("shell", "arduino-app-cli app start $RemoteApp")
    $stopped = $false
    Invoke-Adb @("shell", "arduino-app-cli app logs $RemoteApp --tail 40")
    Write-Output "Rollback snapshot: $rollback"
}
catch {
    if ($stopped) {
        & $AdbPath push (Join-Path $rollback "app.yaml") "$RemoteApp/app.yaml"
        foreach ($name in @("main.py", "event_receiver.py", "classification.py")) {
            $saved = Join-Path $pythonRollback $name
            if (Test-Path -LiteralPath $saved) {
                & $AdbPath push $saved "$RemoteApp/python/$name"
            }
        }
        if (-not $classificationExisted) {
            & $AdbPath shell "rm -f $RemoteApp/python/classification.py"
        }
        if (-not $requirementsExisted) {
            & $AdbPath shell "rm -f $RemoteApp/python/requirements.txt"
        }
        & $AdbPath shell "arduino-app-cli app start $RemoteApp"
    }
    throw
}
