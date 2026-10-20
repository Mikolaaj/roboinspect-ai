#!/usr/bin/env python3
"""Persist local Compose settings without replacing unrelated .env entries."""
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
settings = {
    'ROBOINSPECT_ROOT': str(root),
    'ROBOINSPECT_UID': str(os.getuid()),
    'ROBOINSPECT_GID': str(os.getgid()),
}
path = root / '.env'
lines = path.read_text().splitlines() if path.exists() else []
lines = [line for line in lines if line.partition('=')[0].strip() not in settings]
for key, value in settings.items():
    escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
    lines.append(f'{key}="{escaped}"')
path.write_text('\n'.join(lines) + '\n')
path.chmod(0o600)
