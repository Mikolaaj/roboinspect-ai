#!/usr/bin/env python3
"""Download a pinned local Whisper model once, with a verification manifest."""
import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / 'config/speech.json').read_text())
    destination = ROOT / config['model_directory']
    files = ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt', 'README.md']
    snapshot_download(config['repository'], revision=config['revision'],
                      local_dir=destination, allow_patterns=files)
    checksums = {}
    for name in files:
        with (destination / name).open('rb') as model_file:
            checksums[name] = hashlib.file_digest(model_file, 'sha256').hexdigest()
    manifest = {'repository': config['repository'], 'revision': config['revision'],
                'sha256': checksums}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Whisper gotowy lokalnie:', destination)


if __name__ == '__main__':
    main()
