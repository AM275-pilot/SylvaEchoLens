[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$AdbPath = "$env:LOCALAPPDATA/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe",
    [string]$RemoteApp = "/home/arduino/ArduinoApps/sylvaecholens"
)

$ErrorActionPreference = "Stop"
$expectedOrigin = "https://github.com/AM275-pilot/SylvaEchoLens.git"
$scriptRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$root = (git -C $scriptRoot rev-parse --show-toplevel).Trim()

if ($LASTEXITCODE -ne 0) { throw "The deployment script must run from a Git checkout." }
$root = (Resolve-Path $root).Path
if ($root -ne $scriptRoot) { throw "The scripts directory is not at the repository root: $root" }
if ($RemoteApp -ne "/home/arduino/ArduinoApps/sylvaecholens") {
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

# Record both contents and prior existence so a failed first-time deployment can
# restore absence instead of leaving a mixed application revision behind.
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
$offlineStoreExisted = $false
& $AdbPath shell "test -f $RemoteApp/python/offline_store.py"
if ($LASTEXITCODE -eq 0) {
    $offlineStoreExisted = $true
    Invoke-Adb @(
        "pull", "$RemoteApp/python/offline_store.py",
        (Join-Path $pythonRollback "offline_store.py")
    )
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
$powerManagerExisted = $false
& $AdbPath shell "test -f $RemoteApp/python/power_manager.py"
if ($LASTEXITCODE -eq 0) {
    $powerManagerExisted = $true
    Invoke-Adb @(
        "pull", "$RemoteApp/python/power_manager.py",
        (Join-Path $pythonRollback "power_manager.py")
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
    foreach ($name in @("main.py", "event_receiver.py", "classification.py", "offline_store.py", "power_manager.py", "requirements.txt")) {
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
        foreach ($name in @("main.py", "event_receiver.py")) {
            $saved = Join-Path $pythonRollback $name
            & $AdbPath push $saved "$RemoteApp/python/$name"
        }
        foreach ($entry in @(
            @{ Name = "offline_store.py"; Existed = $offlineStoreExisted },
            @{ Name = "classification.py"; Existed = $classificationExisted },
            @{ Name = "power_manager.py"; Existed = $powerManagerExisted },
            @{ Name = "requirements.txt"; Existed = $requirementsExisted }
        )) {
            $saved = Join-Path $pythonRollback $entry.Name
            if ($entry.Existed) {
                & $AdbPath push $saved "$RemoteApp/python/$($entry.Name)"
            } else {
                & $AdbPath shell "rm -f $RemoteApp/python/$($entry.Name)"
            }
        }
        & $AdbPath shell "arduino-app-cli app start $RemoteApp"
    }
    throw
}
