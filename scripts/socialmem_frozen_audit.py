"""在临时工作区执行封存的只读 checker；不放宽历史 SHA 或改写历史产物。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verified_inventory(directory, files):
    actual = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob('*') if p.is_file()}
    if actual != files:
        raise ValueError('frozen audit inventory mismatch')
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('frozen audit source symlink rejected')


def run_frozen_check(artifact, prepared, entry, expected_seal):
    artifact, prepared = Path(artifact).resolve(), Path(prepared).resolve()
    if sha(artifact / 'seal.json') != expected_seal:
        raise ValueError('historical audit seal mismatch')
    sealed = read(artifact / 'seal.json')
    # 完整文件清单由封存 checker 再校验。此处先绑定 prepare，防止换审计代码。
    if artifact != prepared:
        stage = read(artifact / 'stage.json')
        if Path(stage['input']).resolve() != prepared or stage.get('input_seal_sha256') != sha(prepared / 'seal.json'):
            raise ValueError('historical audit prepare seal binding mismatch')
    prepared_seal = read(prepared / 'seal.json')
    identity = read(prepared / 'identity.json')
    if prepared_seal['files'].get('identity.json') != sha(prepared / 'identity.json'):
        raise ValueError('historical audit identity seal mismatch')
    files = identity['source_files']
    for name, digest in files.items():
        if Path(name).is_absolute() or '..' in Path(name).parts or prepared_seal['files'].get('source/'+name) != digest:
            raise ValueError('historical audit source seal mismatch')
    if entry not in files or not entry.startswith('scripts/') or not entry.endswith('.py'):
        raise ValueError('historical audit entry not frozen')
    verified_inventory(prepared / 'source', files)
    with tempfile.TemporaryDirectory(prefix='starling-frozen-audit-') as temp:
        work = Path(temp)
        shutil.copytree(prepared / 'source', work, dirs_exist_ok=True)
        # 历史程序用 ROOT/build 定位封存来源；只映射既有评测目录。
        build = work / 'build'; build.mkdir(exist_ok=True)
        for path in (ROOT / 'build').glob('socialmem_*'):
            if path.is_dir() and not (build / path.name).exists():
                (build / path.name).symlink_to(path, target_is_directory=True)
        command = [sys.executable, str(work / entry), 'check', '--input', str(artifact)]
        result = subprocess.run(command, cwd=work, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise ValueError('frozen checker execution failed: '+result.stderr[-2000:])
        try: summary = json.loads(result.stdout)
        except ValueError as exc:
            raise ValueError('frozen checker did not produce a verified summary: '+result.stderr[-2000:]) from exc
        if summary.get('state') != sealed['state'] or result.returncode != int(summary['state'] != 'complete'):
            raise ValueError('frozen checker terminal state mismatch')
    verified_inventory(prepared / 'source', files)
    if sha(artifact / 'seal.json') != expected_seal:
        raise ValueError('historical seal changed during audit')
    return dict(returncode=result.returncode, summary=summary, stdout=result.stdout,
                stdout_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(), stderr=result.stderr,
                artifact_seal_sha256=expected_seal, source_files=files, entry=entry)
