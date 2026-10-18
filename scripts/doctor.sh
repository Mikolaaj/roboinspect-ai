#!/usr/bin/env bash
# Read-only inventory; individual missing tools do not stop the report.
set -u
printf '\nSystem\n'
if [ -r /etc/os-release ]; then cat /etc/os-release; fi
printf '\nPython\n'
command -v python3 || true
python3 --version 2>&1 || true
/usr/bin/python3 --version 2>&1 || true
printf '\nTools\n'
for tool in git uv docker ros2 gz g++ pkg-config node; do
    if command -v "$tool" >/dev/null 2>&1; then
        command -v "$tool"
    else
        printf '%s: missing from PATH\n' "$tool"
    fi
done
printf '\nROS installations\n'
if [ -d /opt/ros ]; then ls /opt/ros; fi
printf '\nMemory\n'
free -h 2>&1 || true
printf '\nNVIDIA status (optional)\n'
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 || true
else
    printf 'nvidia-smi is not installed\n'
fi
printf '\nInventory complete. Presence of tools does not confirm a working simulation.\n'
