#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run this uninstaller through sudo.' >&2
    exit 1
fi

power_dir=/home/arduino/ArduinoApps/audio-test/power

systemctl disable --now sylva-linux-suspend.path 2>/dev/null || true
systemctl stop sylva-linux-suspend.service 2>/dev/null || true
rm -f /etc/systemd/system/sylva-linux-suspend.path
rm -f /etc/systemd/system/sylva-linux-suspend.service
rm -f /usr/local/libexec/sylva-linux-suspend
rm -f "$power_dir/helper.ready" "$power_dir/suspend.request" "$power_dir/suspend.result"
systemctl daemon-reload
systemctl reset-failed sylva-linux-suspend.service 2>/dev/null || true

printf '%s\n' 'Sylva Linux suspend helper removed; the application will remain awake.'
