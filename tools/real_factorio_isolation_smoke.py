from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ACKNOWLEDGEMENT = "I understand this starts my supplied Factorio binary"


def snapshot(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    data = json.loads(completed.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("command returned a non-object JSON payload")
    return data


def acquire_operator_lock(instance_root: Path) -> tuple[Path, str]:
    lock_path = instance_root / "locks" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = f"operator-{os.getpid()}-{time.time_ns()}"
    content = {
        "schema": "facman.instance_run_lock.v1",
        "process_id": os.getpid(),
        "created_unix": int(time.time()),
        "token": token,
    }
    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(content, handle, sort_keys=True)
        handle.write("\n")
    return lock_path, token


def release_operator_lock(lock_path: Path, token: str) -> None:
    current = json.loads(lock_path.read_text(encoding="utf-8"))
    if current.get("token") != token:
        raise RuntimeError("run lock token changed; refusing to remove foreign lock")
    lock_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Operator-only real Factorio isolation smoke; never promotes a claim automatically."
    )
    parser.add_argument("--facman", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--factorio-exe", required=True, type=Path)
    parser.add_argument("--protected-root", action="append", default=[], type=Path)
    parser.add_argument("--evidence-out", required=True, type=Path)
    parser.add_argument("--execute-smoke", action="store_true")
    parser.add_argument("--acknowledge", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    preview = run_json(
        [
            str(args.facman),
            "--workspace",
            str(args.workspace),
            "run",
            args.instance_id,
            "--json",
        ]
    )
    preflight = run_json(
        [
            str(args.facman),
            "--workspace",
            str(args.workspace),
            "launch-plan",
            args.instance_id,
            "--preflight",
            "--json",
        ]
    )
    executable = Path(preview["executable"])
    instance_root = Path(preview["effective_config"]["write_data"])
    protected_roots = [Path(preview["app_dir"]), *args.protected_root]
    prepared = {
        "schema": "facman.real_factorio_isolation_smoke.v1",
        "status": "prepared",
        "operator_verdict": "pending",
        "factorio_executable": str(executable),
        "instance_root": str(instance_root),
        "args": preview["args"],
        "preflight": preflight,
        "protected_roots": [str(path) for path in protected_roots],
        "claim_boundary": "Real Factorio isolation remains unproven until a human reviews this evidence.",
    }
    if executable.resolve(strict=False) != args.factorio_exe.resolve(strict=False):
        raise RuntimeError("--factorio-exe does not match the registered launch plan executable")
    if not args.execute_smoke:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(json.dumps(prepared, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(prepared, indent=2))
        return 0
    if args.acknowledge != ACKNOWLEDGEMENT:
        raise RuntimeError(f"--acknowledge must exactly equal: {ACKNOWLEDGEMENT}")
    if preflight.get("status") != "pass":
        raise RuntimeError("authoritative launch preflight did not pass")

    protected_before = {str(path): snapshot(path) for path in protected_roots}
    instance_before = snapshot(instance_root)
    lock_path, token = acquire_operator_lock(instance_root)
    started = time.time()
    try:
        completed = subprocess.run(
            [str(args.factorio_exe), *preview["args"]],
            cwd=args.factorio_exe.parent,
            check=False,
        )
    finally:
        release_operator_lock(lock_path, token)
    protected_after = {str(path): snapshot(path) for path in protected_roots}
    instance_after = snapshot(instance_root)
    changed_protected = [
        path for path in protected_before if protected_before[path] != protected_after[path]
    ]
    changed_instance = sorted(
        set(instance_before) ^ set(instance_after)
        | {
            path
            for path in set(instance_before) & set(instance_after)
            if instance_before[path] != instance_after[path]
        }
    )
    evidence = {
        **prepared,
        "status": "awaiting_operator_verdict",
        "process_exit_status": completed.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "protected_roots_changed": changed_protected,
        "instance_files_changed": changed_instance,
        "operator_verdict": "pending",
    }
    args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if not changed_protected else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"real-factorio-isolation-smoke: {exc}", file=sys.stderr)
        raise SystemExit(2)
