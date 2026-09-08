param(
    [string]$Cli = "$env:LOCALAPPDATA\AppLab\resources\arduino\arduino-cli\arduino-cli.exe",
    [string]$Config = "",
    [string]$ToolchainRoot = "",
    [string]$Port = "COM5",
    [switch]$Upload
)
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
if (-not $ToolchainRoot) { $ToolchainRoot = Join-Path $repo ".codex-build" }
if (-not $Config) { $Config = Join-Path $ToolchainRoot "arduino-cli-custom.yaml" }
$core = Join-Path $ToolchainRoot "arduino-user/hardware/arduino-git/zephyr"
$loader = Join-Path $core "firmwares/zephyr-arduino_uno_q_stm32u585xx.bin"
$expected = "43C4DA2D3F3E6329EB603EBE6922D2DFE8331C9AA50CCC2FC3D7654CA23B39DB"
if (-not (Test-Path $loader)) { throw "Custom loader missing. Follow docs/RUNBOOK.md." }
if ((Get-FileHash $loader -Algorithm SHA256).Hash -ne $expected) {
    throw "Loader differs from the documented word-DMA build. Verify it before deployment."
}
$stage = Join-Path $repo ".codex-build/event-gate-source/sketch"
$build = Join-Path $repo ".codex-build/event-gate-build"
New-Item -ItemType Directory -Force -Path $stage, $build | Out-Null
# The inherited sketch profile selects the stock core; stage sources without it.
Get-ChildItem (Join-Path $repo "app_audio_test/sketch") -File |
    Where-Object { $_.Extension -in ".ino", ".h", ".cpp" } |
    Copy-Item -Destination $stage -Force
& $Cli compile --config-file $Config --fqbn arduino-git:zephyr:unoq --build-path $build $stage
if ($LASTEXITCODE -ne 0) { throw "Sketch compilation failed." }
if ($Upload) {
    & $Cli upload --config-file $Config --fqbn arduino-git:zephyr:unoq --port $Port --input-dir $build
    if ($LASTEXITCODE -ne 0) { throw "Sketch upload failed." }
}
