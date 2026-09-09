# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Exercise actual product-shaped CLI resource discovery without desktop effects."""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile


MAX_CHILD_TIMEOUT_SECONDS = 60.0


def child_timeout_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('timeout must be a number') from error
    if not math.isfinite(seconds) or seconds <= 0 or seconds > MAX_CHILD_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError(
            f'timeout must be greater than zero and at most {MAX_CHILD_TIMEOUT_SECONDS:g} seconds')
    return seconds


def require_export_operation(document, *, effects, recovery=False):
    operation = document["operation"]
    expected = "recovery_required" if recovery else "completed" if effects else "refused_before_effects"
    if (operation["effects_may_have_occurred"] is not effects or operation["outcome"] != expected or
            operation["recovery"]["required"] is not recovery):
        raise AssertionError("resource export operation does not match independently observed effects")
    if recovery and operation["recovery"]["inspect_command"] != "resources.export.inspect":
        raise AssertionError("resource export recovery does not point to its actual inspect route")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): sha(path.read_bytes())
            for path in root.rglob('*') if path.is_file()}


def standalone_pack(path: Path) -> None:
    name = 'content/factorio/test.txt'
    data = b'replaced resource payload'
    digest = sha(data)
    aggregate = sha(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + digest.encode() + b'\n')
    manifest = dict(schema='facman.runtime_resource_pack.v1', version='fixture-1',
                    content_sha256=aggregate, entry_count=1, expanded_bytes=len(data),
                    entries=[dict(path=name, bytes=len(data), sha256=digest)])
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED) as output:
        output.writestr(name, data)
        output.writestr('manifest/resource-pack.v1.json', json.dumps(manifest, separators=(',', ':')))


def run_child(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Serial test runner: children inherit error mode, no machine policy changes."""
    if sys.platform != 'win32':
        return subprocess.run(command, **kwargs)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetErrorMode.restype = ctypes.c_uint
    kernel.SetErrorMode.argtypes = [ctypes.c_uint]
    kernel.SetErrorMode.restype = ctypes.c_uint
    previous = kernel.GetErrorMode()
    # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX.
    # Keep failure status observable rather than waiting on interactive dialogs.
    kernel.SetErrorMode(previous | 0x8003)
    try:
        return subprocess.run(command, **kwargs)
    finally:
        kernel.SetErrorMode(previous)


def capture(label: str, command: list[str], records: list[dict], **kwargs) -> dict:
    # CTest retains child output on failure.  Emit the phase before dispatch so
    # an outer CTest timeout identifies a slow child instead of losing the
    # in-memory receipt that is written only after the full proof completes.
    print(json.dumps(dict(event='start', label=label)), file=sys.stderr, flush=True)
    started = time.monotonic()
    try:
        result = run_child(command, **kwargs)
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b'', error.stderr or b''
        records.append(dict(label=label, command=command, executable=kwargs.get('executable'),
                            exit_code=None, timed_out=True, seconds=time.monotonic()-started,
                            stdout=stdout.decode('utf-8', 'replace'), stderr=stderr.decode('utf-8', 'replace'),
                            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        raise
    record = dict(label=label, command=command, executable=kwargs.get('executable'),
                  exit_code=result.returncode, timed_out=False, seconds=time.monotonic()-started,
                  stdout=result.stdout.decode('utf-8', 'replace'),
                  stderr=result.stderr.decode('utf-8', 'replace'),
                  stdout_sha256=sha(result.stdout), stderr_sha256=sha(result.stderr))
    records.append(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--runtime-file', type=Path, action='append', default=[])
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--fixture-timeout-seconds', type=child_timeout_seconds, default=30.0)
    args = parser.parse_args()
    platform = 'windows' if sys.platform == 'win32' else 'macos' if sys.platform == 'darwin' else 'linux'
    parent = args.work_root.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / uuid.uuid4().hex
    root.mkdir()
    records: list[dict[str, object]] = []
    cli_relative = Path('bin/facman.exe' if platform == 'windows' else 'Contents/Helpers/facman' if platform == 'macos' else 'facman')
    manifest_relative = Path('manifest/package.v1.toml' if platform == 'windows' else 'Contents/Resources/manifest/product-stage.v1.json' if platform == 'macos' else 'share/facman/manifest/product-stage.v1.json')
    resource_relative = Path('facman.resources' if platform == 'windows' else 'Contents/Resources/facman.resources' if platform == 'macos' else 'share/facman/facman.resources')
    clean_env = dict(os.environ)
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'FACMAN_RESOURCE_PACK'):
        clean_env.pop(key, None)
    foreign_cwd = root / 'foreign-cwd'
    foreign_cwd.mkdir()
    started = time.monotonic()

    def run(label: str, command: list[str], *, environment: dict[str, str] | None = None,
            executable: str | None = None, ok: bool = True,
            timeout_seconds: float = 30.0) -> str:
        record = capture(label, command, records, executable=executable, cwd=foreign_cwd,
                         env=environment or clean_env, capture_output=True,
                         timeout=timeout_seconds)
        if (record['exit_code'] == 0) != ok:
            raise AssertionError(f'{label}: exit={record["exit_code"]}; stdout={record["stdout"]}; stderr={record["stderr"]}')
        return record['stdout']

    runtime_inputs = []
    try:
        for path in args.runtime_file:
            if platform != 'windows' or path.suffix != '.dll' or not path.is_file():
                raise AssertionError('runtime fixture input must be an existing Windows DLL')
            runtime_inputs.append(dict(path=str(path.resolve()), name=path.name,
                                       bytes=path.stat().st_size, sha256=sha(path.read_bytes())))
        if len({p['name'].lower() for p in runtime_inputs}) != len(runtime_inputs):
            raise AssertionError('runtime fixture input names collide')
        seed = root / 'seed'
        run('prepare_fixture', [str(args.fixture.resolve()), '--make-fixture', platform,
                               str(seed), str(args.cli.resolve()),
                               *[p['path'] for p in runtime_inputs]],
            timeout_seconds=args.fixture_timeout_seconds)
        for item in runtime_inputs:
            copied = seed / cli_relative.parent / item['name']
            if sha(copied.read_bytes()) != item['sha256'] or copied.stat().st_size != item['bytes']:
                raise AssertionError('fixture runtime differs from exact CMake input')
        expected_resource_hash = sha((seed / resource_relative).read_bytes())
        for mode in ('portable', 'installed-stage'):
            product = root / f'{mode} relocated \u00e9 \u03b2'
            if platform == 'macos':
                product /= 'FacMan.app'
            shutil.copytree(seed, product)
            cli = product / cli_relative
            before = inventory(product)
            output = run(mode + '_relocated', [str(cli), 'resources', 'verify', '--json'])
            payload = json.loads(output)['payload']
            if (payload['pack_sha256'] != expected_resource_hash or
                    payload['package_profile'] != f'{platform}_product_x64' or
                    payload['package_manifest_sha256'] != sha((product / manifest_relative).read_bytes()) or
                    payload['entries'] != ['content/factorio/test.txt'] or
                    payload['expanded_bytes'] != len(b'original resource payload')):
                raise AssertionError('default resources output differs from independent product identity')
            # These fixtures intentionally have the same native layout; the
            # second relocated copy proves its own process-image discovery
            # without repeatedly launching every identical terminal boundary.
            # This keeps the sanitizer proof within CTest's fixed total budget.
            if mode == 'installed-stage':
                if inventory(product) != before:
                    raise AssertionError('relocated terminal resource check changed product bytes')
                continue
            run(mode + '_spoofed_argv0', ['foreign-argv0', 'resources', 'verify', '--json'], executable=str(cli))
            run(mode + '_version_no_display', [str(cli), '--version'])
            run(mode + '_help_no_display', [str(cli), '--help'])
            if inventory(product) != before:
                raise AssertionError('read-only terminal resource checks changed product bytes')
            if platform != 'windows':
                path_env = dict(clean_env, PATH=str(cli.parent) + os.pathsep + clean_env.get('PATH', ''))
                run(mode + '_path_lookup', [cli.name, 'resources', 'verify', '--json'], environment=path_env)
            original = (product / resource_relative).read_bytes()
            original_mode = stat.S_IMODE((product / resource_relative).stat().st_mode)
            (product / resource_relative).unlink()
            missing = run(mode + '_missing', [str(cli), 'resources', 'verify', '--json'], ok=False)
            if 'resource_' not in missing:
                raise AssertionError('missing resource lacks typed refusal')
            run(mode + '_help_when_missing', [str(cli), '--help'])
            (product / resource_relative).write_bytes(original[:-1])
            (product / resource_relative).chmod(original_mode)
            run(mode + '_truncated', [str(cli), 'resources', 'verify', '--json'], ok=False)
            (product / resource_relative).write_bytes(original)
            (product / resource_relative).chmod(original_mode)
            destination = root / (mode + '-export')
            exported = run(mode + '_export', [str(cli), 'resources', 'export', str(destination), '--json'])
            require_export_operation(json.loads(exported), effects=True)
            if (destination / 'content/factorio/test.txt').read_bytes() != b'original resource payload':
                raise AssertionError('product export differs from independent original payload')
            refused = run(mode + '_export_existing', [str(cli), 'resources', 'export', str(destination), '--json'], ok=False)
            require_export_operation(json.loads(refused), effects=False)
            destination_before = inventory(destination)
            observed = json.loads(run(mode + '_inspect_export',
                [str(cli), 'resources', 'inspect-export', str(destination), '--json']))
            if (observed['command'] != 'resources.export.inspect' or
                    observed['operation']['effects_may_have_occurred'] is not False or
                    observed['payload']['scope'] != 'destination_type_and_identity_only' or
                    observed['payload']['state'] != 'present' or inventory(destination) != destination_before):
                raise AssertionError('destination inspection differs from read-only type/identity contract')
            if inventory(product) != before:
                raise AssertionError('resource operations changed restored product bytes')
        # Deliberate loader failures live in fresh private copies. The dependency
        # bytes are retained outside the loader search location, never deleted.
        for index, item in enumerate(runtime_inputs):
            product = root / f'missing-runtime-{index}'
            shutil.copytree(seed, product)
            missing = product / cli_relative.parent / item['name']
            missing.rename(root / f'retained-runtime-{index}.dll')
            record = capture('missing_runtime_' + item['name'],
                             [str(product / cli_relative), '--version'], records,
                             cwd=foreign_cwd, env=clean_env, capture_output=True, timeout=8)
            if record['exit_code'] & 0xffffffff != 0xc0000135:
                raise AssertionError('missing provider DLL did not produce STATUS_DLL_NOT_FOUND')
        for item in runtime_inputs:
            if sha(Path(item['path']).read_bytes()) != item['sha256']:
                raise AssertionError('original runtime input changed during fixture proof')
        foreign = root / 'explicit.resources'
        standalone_pack(foreign)
        cli = seed / cli_relative
        explicit = run('explicit_pack', [str(cli), 'resources', 'verify', '--pack', str(foreign), '--json'])
        if 'package_profile' in explicit:
            raise AssertionError('standalone inspection gained package identity')
        selected_env = dict(clean_env, FACMAN_RESOURCE_PACK=str(foreign))
        selected = run('explicit_environment_pack', [str(cli), 'resources', 'verify', '--json'], environment=selected_env)
        if 'package_profile' in selected:
            raise AssertionError('environment inspection gained package identity')
        run('explicit_pack_precedes_environment',
            [str(cli), 'resources', 'verify', '--pack', str(foreign), '--json'],
            environment=dict(clean_env, FACMAN_RESOURCE_PACK=str(root / 'absent.resources')))
        run('missing_explicit_pack', [str(cli), 'resources', 'verify', '--pack', str(root / 'absent.resources'), '--json'], ok=False)
        outcome = 'PASS'
    except Exception as error:
        outcome = 'FAIL'
        records.append(dict(label='exception', error=str(error)))
    receipt = dict(schema='facman.resource_identity_cli_proof.v1', result=outcome,
                   platform=sys.platform, fixture_only=True, process_image_cli_sha256=sha(args.cli.read_bytes()),
                   fixture_executable_sha256=sha(args.fixture.read_bytes()),
                   runtime_inputs=runtime_inputs,
                   seconds=time.monotonic()-started, commands=records,
                   authority=dict(human=False, game=False, live_installation=False, publication=False, beta1=False))
    receipt_path = root / 'validation.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(result=outcome, receipt=str(receipt_path), sha256=sha(receipt_path.read_bytes()),
                          commands=len(records)), indent=2))
    if outcome != 'PASS':
        print(records[-1], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
