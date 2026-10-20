#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Exercise real low-space backup refusal with an explicit packaged Linux CLI."""

from __future__ import annotations

import argparse
import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

sys.dont_write_bytecode = True
VOLUME_BYTES = 4 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'proof input contains a symlink: {path}')
        if path.is_file():
            value = sha256(path)
        elif path.is_dir():
            value = 'directory'
        else:
            raise ValueError(f'proof input contains a non-regular entry: {path}')
        result[path.relative_to(root).as_posix()] = value
    return result


def entries(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob('*')}


def worker(args: argparse.Namespace, work: Path) -> int:
    namespace = os.readlink('/proc/self/ns/mnt')
    parent_namespace = os.readlink(f'/proc/{os.getppid()}/ns/mnt')
    if (os.geteuid() != 0 or namespace == args.parent_namespace
            or parent_namespace != args.parent_namespace):
        raise ValueError('worker requires an isolated privileged mount namespace')
    subprocess.run(['mount', '--make-rprivate', '/'], check=True, timeout=10)
    work.mkdir()
    mounted: list[Path] = []
    commands: list[dict] = []
    report = dict(schema='facman.scoped_produced_package_test.v1', status='fail',
        extracted_cli_sha256=sha256(args.executable), commands=commands,
        host=dict(uname=list(os.uname()), uid=os.geteuid(),
                  mount_namespace=namespace, parent_mount_namespace=args.parent_namespace),
        fault_injection=False, volume_limit_bytes=VOLUME_BYTES,
        qualification=dict(release=False, support=False, game=False, human=False),
        scope='Explicit packaged CLI on a real Linux test host; caller owns package/source custody and final qualification.')
    environment = {k: v for k, v in os.environ.items() if not k.startswith('FACMAN_TEST_')}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'

    def invoke(label: str, arguments: list[str], expected: int = 0) -> tuple[dict, dict]:
        argv = [str(args.executable), '--workspace', str(workspace), *arguments, '--json']
        result = subprocess.run(argv, cwd=work, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding='utf-8', timeout=30)
        for suffix, output in [('stdout', result.stdout), ('stderr', result.stderr)]:
            (work/(label+'.'+suffix)).write_text(output, encoding='utf-8')
        commands.append(dict(label=label, argv=argv, exit=result.returncode))
        if result.returncode != expected:
            raise ValueError(f'{label}: exit {result.returncode}, expected {expected}; {result.stdout[-2048:]} {result.stderr[-2048:]}')
        envelope = json.loads(result.stdout)
        assert envelope['schema'] == 'facman.transport_response.v2'
        assert isinstance(envelope['payload'], dict)
        return envelope['payload'], envelope

    try:
        before_package = inventory(args.package_root)
        fixture = args.source_root/'tests/fixtures/fake_factorio_install'
        fixture_before = inventory(fixture)
        for name in ['workspace-volume', 'destination-volume']:
            target = work/name
            target.mkdir()
            subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=4M,nodev,nosuid,noexec',
                            'facman-world-backup-proof', str(target)], check=True, timeout=10)
            mounted.append(target)
        workspace = mounted[0]/'workspace'
        destination = mounted[1]
        initial = shutil.disk_usage(destination)
        assert initial.total == VOLUME_BYTES
        invoke('register', ['installs', 'import', str(fixture), '--id', 'fixture'])
        invoke('instance', ['instances', 'create', 'Low Space Probe', '--install', 'fixture'])
        source = workspace/'instances/low-space-probe/saves/world.zip'
        shutil.copyfile(args.source_root/'tests/fixtures/factorio_saves/valid_simple_save/starter.zip', source)
        source_hash = sha256(source)
        kept = destination/'kept.backup.zip'
        positive, _ = invoke('positive', ['saves', 'backup', 'world', '--instance',
            'low-space-probe', '--to', str(kept)])
        assert positive['schema'] == 'factorio.save_backup.v1'
        assert positive['sha256'] == sha256(kept) == source_hash
        assert positive['consistency_policy'] == 'pinned_source_two_pass_sha256_v1'
        assert entries(destination) == {'kept.backup.zip', 'kept.backup.zip.manifest.json'}
        retained = inventory(destination)
        filler = destination/'owned-capacity-filler'
        written = 0
        with filler.open('xb', buffering=0) as handle:
            for _ in range(VOLUME_BYTES // 4096 + 1):
                try:
                    count = handle.write(b'\0'*4096)
                    assert count > 0
                    written += count
                except OSError as error:
                    if error.errno != errno.ENOSPC:
                        raise
                    break
            else:
                raise ValueError('bounded tmpfs did not produce ENOSPC')
        full = shutil.disk_usage(destination)
        assert full.free == 0 and written <= VOLUME_BYTES
        target = destination/'retry.backup.zip'
        arguments = ['saves', 'backup', 'world', '--instance', 'low-space-probe', '--to', str(target)]
        refused, envelope = invoke('refused', arguments, expected=1)
        assert refused['refusal']['code'] == 'persistent_write_refused'
        assert refused['refusal']['reason'] == 'Insufficient space for a complete backup stage'
        assert refused['refusal']['recoverable'] and refused['refusal']['retryable']
        assert envelope['operation']['outcome'] == 'refused_before_effects'
        assert envelope['operation']['effects_may_have_occurred'] is False
        assert not target.exists() and not Path(str(target)+'.manifest.json').exists()
        assert sha256(source) == source_hash
        assert {name: sha256(destination/name) for name in retained} == retained
        assert entries(destination) == set(retained) | {filler.name}
        assert not list(workspace.rglob('.facman-copy-*'))
        assert not list(workspace.rglob('.facman-save-backup-*'))
        filler.unlink()
        restored = shutil.disk_usage(destination)
        assert restored.free >= source.stat().st_size + 128*1024
        retry, _ = invoke('same-target-retry', arguments)
        assert retry['schema'] == 'factorio.save_backup.v1'
        assert retry['sha256'] == sha256(target) == source_hash
        assert sha256(source) == source_hash
        assert {name: sha256(destination/name) for name in retained} == retained
        assert entries(destination) == set(retained) | {'retry.backup.zip', 'retry.backup.zip.manifest.json'}
        assert inventory(args.package_root) == before_package
        assert inventory(fixture) == fixture_before
        report.update(status='pass', source_sha256=source_hash, retained_backup_hashes=retained,
            capacity=dict(initial=list(initial), full=list(full), restored=list(restored), filler_bytes=written),
            refusal=refused['refusal'], same_target_retry=True,
            checks=['positive_backup', 'real_kernel_ENOSPC', 'typed_refusal_before_effects',
                    'source_and_prior_backup_preserved', 'no_partial_backup_or_stage',
                    'same_target_retry_after_capacity_restored', 'package_and_fixture_preserved'])
    except BaseException as error:
        report['error'] = repr(error)
    finally:
        cleanup = []
        for target in reversed(mounted):
            try:
                subprocess.run(['umount', str(target)], check=True, timeout=10)
                cleanup.append(dict(target=str(target), unmounted=True))
            except (OSError, subprocess.SubprocessError) as error:
                report.update(status='fail', cleanup_error=repr(error))
                cleanup.append(dict(target=str(target), unmounted=False))
        report['cleanup'] = cleanup
        report['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with args.evidence.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'commands'}))
    return 0 if report['status'] == 'pass' else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--package-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--parent-namespace', default='', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise ValueError('real Linux mount namespaces and tmpfs are required')
    args.executable = args.executable.resolve(strict=True)
    args.package_root = args.package_root.resolve(strict=True)
    args.source_root = args.source_root.resolve(strict=True)
    args.evidence = args.evidence.parent.resolve(strict=True)/args.evidence.name
    if not __debug__:
        raise ValueError('proof assertions must remain enabled; remove Python optimization')
    if not args.executable.is_file() or not args.executable.is_relative_to(args.package_root):
        raise ValueError('executable must belong to the explicit package root')
    if args.evidence.exists() or not args.evidence.parent.is_dir():
        raise ValueError('evidence needs an existing managed parent and a new filename')
    work = args.evidence.with_name(args.evidence.stem+'-work')
    if work.exists():
        raise ValueError('retain prior attempt; work destination already exists')
    if args.evidence.is_relative_to(args.package_root) or args.evidence.is_relative_to(args.source_root):
        raise ValueError('evidence must be outside source and package')
    if args.worker:
        return worker(args, work)
    namespace = os.readlink('/proc/self/ns/mnt')
    command = ['unshare', '--mount', '--propagation', 'private', sys.executable, '-B',
        str(Path(__file__).resolve()), '--worker', '--parent-namespace', namespace,
        '--executable', str(args.executable), '--package-root', str(args.package_root),
        '--source-root', str(args.source_root), '--evidence', str(args.evidence)]
    if os.geteuid() != 0:
        command = ['sudo', '-n', '--', *command]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with args.evidence.with_suffix('.runner.log').open('x', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=environment, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            status = process.wait(timeout=240)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
            raise ValueError('isolated proof exceeded its deadline; inspect retained runner log')
    if status != 0 or not args.evidence.is_file():
        raise ValueError(f'isolated proof failed with exit {status}; inspect retained runner log')
    report = json.loads(args.evidence.read_text(encoding='utf-8'))
    assert report['status'] == 'pass'
    print(json.dumps(dict(status='pass', evidence=str(args.evidence),
        extracted_cli_sha256=report['extracted_cli_sha256'], same_target_retry=report['same_target_retry'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
