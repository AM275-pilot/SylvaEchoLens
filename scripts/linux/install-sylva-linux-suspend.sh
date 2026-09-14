#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run this installer through sudo.' >&2
    exit 1
fi

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
power_dir=/home/arduino/ArduinoApps/audio-test/power

install -d -m 0755 /usr/local/libexec
install -m 0755 "$source_dir/sylva-linux-suspend" /usr/local/libexec/sylva-linux-suspend
install -m 0644 "$source_dir/sylva-linux-suspend.service" /etc/systemd/system/sylva-linux-suspend.service
install -m 0644 "$source_dir/sylva-linux-suspend.path" /etc/systemd/system/sylva-linux-suspend.path
install -d -o arduino -g arduino -m 0755 "$power_dir"
rm -f "$power_dir/suspend.request" "$power_dir/suspend.result"
printf '%s\n' freeze > "$power_dir/helper.ready"
chown arduino:arduino "$power_dir/helper.ready"
chmod 0644 "$power_dir/helper.ready"

systemctl daemon-reload
systemctl enable --now sylva-linux-suspend.path
printf '%s\n' 'Sylva Linux suspend helper installed; supported mode: freeze'
