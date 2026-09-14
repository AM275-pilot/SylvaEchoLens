param(
    [string]$AdbPath = "$env:LOCALAPPDATA/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe"
)

$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "linux"
$remote = "/home/arduino/sylva-power-install"

if (-not (Test-Path -LiteralPath $AdbPath)) { throw "ADB not found: $AdbPath" }

function Invoke-Adb([string[]]$Arguments) {
    & $AdbPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "ADB failed: $($Arguments -join ' ')" }
}

Invoke-Adb @("get-state")
Invoke-Adb @("shell", "mkdir -p $remote")
foreach ($name in @(
    "sylva-linux-suspend",
    "sylva-linux-suspend.service",
    "sylva-linux-suspend.path",
    "install-sylva-linux-suspend.sh",
    "uninstall-sylva-linux-suspend.sh"
)) {
    Invoke-Adb @("push", (Join-Path $source $name), "$remote/$name")
}
Invoke-Adb @("shell", "chmod 0755 $remote/install-sylva-linux-suspend.sh $remote/uninstall-sylva-linux-suspend.sh $remote/sylva-linux-suspend")
Invoke-Adb @("shell", "chmod 0644 $remote/sylva-linux-suspend.service $remote/sylva-linux-suspend.path")

# Installation changes host power policy and therefore requires the board owner's
# sudo authentication. Try passwordless sudo, then print the exact interactive step.
& $AdbPath shell "sudo -n $remote/install-sylva-linux-suspend.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Files are staged, but the privileged helper is not installed."
    Write-Output "Run interactively: adb shell -t 'sudo $remote/install-sylva-linux-suspend.sh'"
    exit 2
}

Write-Output "Linux suspend helper installed and enabled."
