# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import development_layout  # noqa: E402

LEGACY_NAMES = {"build", "out", "tmp", "tasks", ".worktrees", ".validation"}
LEGACY_PREFIXES = ("facman", ".facman", "aide-q")
SHARED_PRUNABLE_ROOT_NAMES = {".archives", ".backups", ".evidence"}
IN_TREE_OUTPUT_NAMES = ("build", "dist", "out", "tmp", ".worktrees")
RELEASE_TAG = re.compile(r"^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
FORBIDDEN_BRANCH_PREFIXES = ("backup/", "evidence/", "proof/", "safety/")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(detail or f"git {' '.join(args)} failed")
    return completed


def is_reparse_or_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def directory_inventory(path: Path) -> tuple[int, int, list[Path]]:
    def raise_walk_error(error: OSError) -> None:
        raise error

    files = 0
    total = 0
    links: list[Path] = []
    for current, directories, names in os.walk(
        path, followlinks=False, onerror=raise_walk_error
    ):
        current_path = Path(current)
        linked_directories = [
            current_path / name
            for name in directories
            if is_reparse_or_link(current_path / name)
        ]
        links.extend(linked_directories)
        directories[:] = [
            name for name in directories if current_path / name not in linked_directories
        ]
        for name in names:
            candidate = current_path / name
            if is_reparse_or_link(candidate):
                links.append(candidate)
                continue
            try:
                total += candidate.stat().st_size
                files += 1
            except OSError:
                continue
    return files, total, links


def directory_size(path: Path) -> tuple[int, int]:
    files, total, _ = directory_inventory(path)
    return files, total


def remove_tree(path: Path) -> None:
    def clear_readonly_and_retry(function: Any, candidate: str, exc_info: Any) -> None:
        error = exc_info[1]
        if not isinstance(error, PermissionError):
            raise error
        os.chmod(candidate, stat.S_IWRITE)
        function(candidate)

    _, _, links = directory_inventory(path)
    for link in sorted(links, key=lambda item: len(item.parts), reverse=True):
        if not os.path.lexists(link):
            continue
        try:
            link.unlink()
        except (IsADirectoryError, PermissionError):
            os.rmdir(link)
        if os.path.lexists(link):
            raise ValueError(f"failed to unlink contained reparse point: {link}")
    shutil.rmtree(path, onerror=clear_readonly_and_retry)


def task_roots(source_root: Path) -> list[Path]:
    parent = development_layout.repository_root(source_root) / "tasks"
    if not parent.is_dir():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir())


def task_root_record(path: Path, *, measure: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path.resolve()), "owned": False}
    try:
        marker = development_layout.read_marker(path, ROOT)
    except ValueError as exc:
        record["error"] = str(exc)
        return record
    record.update(
        {
            "owned": True,
            "task_id": marker.get("task_id"),
            "created_at": marker.get("created_at"),
            "last_used_at": marker.get("last_used_at"),
        }
    )
    if measure:
        files, size = directory_size(path)
        record.update({"files": files, "bytes": size})
    return record


def worktree_records(base: str) -> list[dict[str, Any]]:
    output = git("worktree", "list", "--porcelain").stdout.splitlines()
    raw: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in [*output, ""]:
        if not line:
            if current:
                raw.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    records: list[dict[str, Any]] = []
    managed_root = development_layout.worktree_root(ROOT).resolve()
    for item in raw:
        path = Path(item["worktree"]).resolve()
        head = item.get("HEAD", "")
        primary = path == ROOT.resolve()
        contained = primary or git("merge-base", "--is-ancestor", head, base, check=False).returncode == 0
        status = [] if not path.exists() else git(
            "-C", str(path), "status", "--porcelain=v1", "--untracked-files=normal"
        ).stdout.splitlines()
        records.append(
            {
                "path": str(path),
                "head": head,
                "branch": item.get("branch", "detached").removeprefix("refs/heads/"),
                "primary": primary,
                "managed_location": primary or path.is_relative_to(managed_root),
                "contained_in_base": contained,
                "clean": not status,
                "cleanup_eligible": (
                    not primary
                    and path.is_relative_to(managed_root)
                    and contained
                    and not status
                ),
            }
        )
    return records


def ref_records(base: str) -> dict[str, Any]:
    current = git("branch", "--show-current").stdout.strip()
    local_names = [
        line.strip()
        for line in git("for-each-ref", "--format=%(refname:short)", "refs/heads").stdout.splitlines()
        if line.strip()
    ]
    remote_names = [
        line.strip()
        for line in git(
            "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"
        ).stdout.splitlines()
        if line.strip() and line.strip() not in {"origin", "origin/HEAD"}
    ]
    tags = [
        line.strip()
        for line in git("tag", "--list").stdout.splitlines()
        if line.strip()
    ]
    local: list[dict[str, Any]] = []
    for name in local_names:
        contained = git("merge-base", "--is-ancestor", name, base, check=False).returncode == 0
        local.append(
            {
                "name": name,
                "current": name == current,
                "core": name in {"main", "dev"},
                "contained_in_base": contained,
                "cleanup_candidate": name != current and name not in {"main", "dev"} and contained,
                "forbidden_prefix": name.startswith(FORBIDDEN_BRANCH_PREFIXES),
            }
        )
    return {
        "current_branch": current or None,
        "local_branches": local,
        "remote_branches": remote_names,
        "tags": [
            {"name": name, "release_tag": bool(RELEASE_TAG.fullmatch(name))}
            for name in tags
        ],
    }


def command_paths(args: argparse.Namespace) -> int:
    task_id = development_layout.current_task_id(ROOT)
    payload = {
        "schema": "facman.development_layout.v1",
        "source_root": str(ROOT.resolve()),
        "development_base": str(development_layout.development_base()),
        "repository_root": str(development_layout.repository_root(ROOT)),
        "task_id": task_id,
        "task_root": str(development_layout.task_root(ROOT, task_id)),
        "worktree_root": str(development_layout.worktree_root(ROOT)),
        "retention_days": development_layout.DEFAULT_RETENTION_DAYS,
        "max_task_roots": development_layout.DEFAULT_MAX_TASK_ROOTS,
        "max_bytes": development_layout.DEFAULT_MAX_BYTES,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    roots = [task_root_record(path, measure=args.measure) for path in task_roots(ROOT)]
    worktrees = worktree_records(args.base)
    refs = ref_records(args.base)
    in_tree_outputs = [
        str((ROOT / name).resolve())
        for name in IN_TREE_OUTPUT_NAMES
        if (ROOT / name).exists()
    ]
    violations: list[str] = []
    if len(roots) > args.max_task_roots:
        violations.append(f"task_root_count_exceeds_{args.max_task_roots}")
    unowned = [record["path"] for record in roots if not record["owned"]]
    if unowned:
        violations.append("unowned_task_roots_present")
    if args.measure:
        total = sum(int(record.get("bytes", 0)) for record in roots)
        if total > args.max_bytes:
            violations.append(f"task_root_bytes_exceed_{args.max_bytes}")
    else:
        total = None
    secondary = [record for record in worktrees if not record["primary"]]
    if len(secondary) > args.max_worktrees:
        violations.append(f"secondary_worktree_count_exceeds_{args.max_worktrees}")
    if any(not record["managed_location"] for record in secondary):
        violations.append("unmanaged_secondary_worktrees_present")
    if in_tree_outputs:
        violations.append("in_tree_output_roots_present")
    if any(record["cleanup_candidate"] for record in refs["local_branches"]):
        violations.append("merged_local_task_branches_present")
    if any(record["forbidden_prefix"] for record in refs["local_branches"]):
        violations.append("forbidden_permanent_branch_prefix_present")
    if any(not record["release_tag"] for record in refs["tags"]):
        violations.append("nonrelease_tags_present")
    payload = {
        "schema": "facman.workspace_hygiene_report.v1",
        "result": "pass" if not violations else "fail",
        "violations": violations,
        "task_roots": roots,
        "task_root_bytes": total,
        "worktrees": worktrees,
        "refs": refs,
        "in_tree_output_roots": in_tree_outputs,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not violations else 1


def parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("development marker has no last_used_at timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def command_clean(args: argparse.Namespace) -> int:
    current = development_layout.task_root(ROOT, development_layout.current_task_id(ROOT)).resolve()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_age_days)
    candidates: list[dict[str, Any]] = []
    for path in task_roots(ROOT):
        marker = development_layout.read_marker(path, ROOT)
        eligible = parse_time(marker.get("last_used_at")) < cutoff
        reason = "expired" if eligible else "retained_recent"
        if path.resolve() == current and not args.include_current:
            eligible = False
            reason = "retained_current"
        record = {"path": str(path.resolve()), "eligible": eligible, "reason": reason}
        if eligible and args.apply:
            if is_reparse_or_link(path):
                raise ValueError(f"refusing linked development root: {path.resolve()}")
            development_layout.read_marker(path, ROOT)
            remove_tree(path)
            record["removed"] = True
        candidates.append(record)
    print(
        json.dumps(
            {
                "schema": "facman.workspace_hygiene_cleanup.v1",
                "mode": "apply" if args.apply else "plan",
                "candidates": candidates,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_worktrees(args: argparse.Namespace) -> int:
    records = worktree_records(args.base)
    for record in records:
        if not record["cleanup_eligible"] or not args.apply:
            continue
        path = Path(str(record["path"]))
        if is_reparse_or_link(path):
            raise ValueError(f"refusing linked worktree: {path}")
        git("worktree", "remove", "--force", str(path))
        record["removed"] = True
    if args.apply:
        git("worktree", "prune", "--expire", "now")
    print(
        json.dumps(
            {
                "schema": "facman.workspace_hygiene_worktrees.v1",
                "mode": "apply" if args.apply else "plan",
                "base": args.base,
                "worktrees": records,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_worktree_add(args: argparse.Namespace) -> int:
    branch = args.branch.strip()
    if not branch.startswith("task/"):
        raise ValueError("managed worktree branches must use the task/ prefix")
    if git("check-ref-format", "--branch", branch, check=False).returncode:
        raise ValueError(f"invalid task branch name: {branch}")
    if git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0:
        raise ValueError(f"local branch already exists: {branch}")
    git("rev-parse", "--verify", f"{args.start}^{{commit}}")
    secondary = [record for record in worktree_records(args.cleanup_base) if not record["primary"]]
    if len(secondary) >= args.max_worktrees:
        raise ValueError(
            f"secondary worktree limit {args.max_worktrees} is already reached"
        )
    target = (development_layout.worktree_root(ROOT) / development_layout.slug(branch)).resolve()
    managed_root = development_layout.worktree_root(ROOT).resolve()
    if not target.is_relative_to(managed_root) or target == managed_root:
        raise ValueError(f"managed worktree target escaped its root: {target}")
    if os.path.lexists(target):
        raise ValueError(f"managed worktree target already exists: {target}")
    managed_root.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-b", branch, str(target), args.start)
    print(
        json.dumps(
            {
                "schema": "facman.workspace_hygiene_worktree_add.v1",
                "branch": branch,
                "start": args.start,
                "path": str(target),
                "max_worktrees": args.max_worktrees,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def recognized_legacy_name(path: Path) -> bool:
    name = path.name.lower()
    return name in LEGACY_NAMES or name.startswith(LEGACY_PREFIXES)


def validate_legacy_path(
    path: Path,
    allowed_roots: list[Path],
    allow_filesystem_root: bool,
    *,
    allow_shared_prunable_root: bool = False,
) -> Path:
    unresolved = Path(os.path.abspath(path.expanduser()))
    if not os.path.lexists(unresolved):
        raise ValueError(f"legacy target does not exist: {unresolved}")
    if is_reparse_or_link(unresolved):
        raise ValueError(f"legacy target is a link or reparse point: {unresolved}")
    resolved = unresolved.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"legacy target is not a directory: {resolved}")
    if is_reparse_or_link(resolved):
        raise ValueError(f"legacy target is a link or reparse point: {resolved}")
    protected = [ROOT.resolve(), Path.home().resolve()]
    if any(resolved == item or item.is_relative_to(resolved) for item in protected):
        raise ValueError(f"legacy target is protected or contains a protected root: {resolved}")
    accepted = False
    for allowed in allowed_roots:
        root = allowed.resolve(strict=True)
        if root == Path(root.anchor) and not allow_filesystem_root:
            raise ValueError(f"filesystem-root allowlist requires --allow-filesystem-root: {root}")
        if resolved != root and resolved.is_relative_to(root):
            accepted = True
            break
    if not accepted:
        raise ValueError(f"legacy target is outside the exact allowed roots: {resolved}")
    shared_prunable = (
        allow_shared_prunable_root
        and resolved.name.casefold() in SHARED_PRUNABLE_ROOT_NAMES
    )
    if not recognized_legacy_name(resolved) and not shared_prunable:
        raise ValueError(f"legacy target name is not recognized as disposable: {resolved}")
    return resolved


def command_legacy_clean(args: argparse.Namespace) -> int:
    if args.apply and not args.acknowledge_unowned:
        raise ValueError("--apply requires --acknowledge-unowned")
    allowed = [Path(value).expanduser() for value in args.allowed_root]
    if not args.path and not args.discover_direct_children:
        raise ValueError("provide --path or --discover-direct-children")
    targets = [
        validate_legacy_path(Path(value).expanduser(), allowed, args.allow_filesystem_root)
        for value in (args.path or [])
    ]
    errors: list[dict[str, str]] = []
    excluded = {value.casefold() for value in args.exclude_name}
    if args.discover_direct_children:
        for allowed_root in allowed:
            root = allowed_root.resolve(strict=True)
            if root == Path(root.anchor) and not args.allow_filesystem_root:
                raise ValueError(
                    f"filesystem-root allowlist requires --allow-filesystem-root: {root}"
                )
            for child in root.iterdir():
                if child.name.casefold() in excluded or not recognized_legacy_name(child):
                    continue
                try:
                    if is_reparse_or_link(child):
                        raise ValueError(
                            f"legacy target is a link or reparse point: {child}"
                        )
                    if not child.is_dir():
                        continue
                    targets.append(
                        validate_legacy_path(child, allowed, args.allow_filesystem_root)
                    )
                except (OSError, ValueError) as exc:
                    errors.append({"path": str(child), "error": str(exc)})
    targets = sorted(set(targets), key=lambda item: str(item).casefold())
    records: list[dict[str, Any]] = []
    for target in targets:
        record: dict[str, Any] = {"path": str(target), "removed": False}
        try:
            files, size, links = directory_inventory(target)
            record.update(
                {
                    "files": files,
                    "bytes": size,
                    "contained_reparse_points": [str(path) for path in links],
                }
            )
            if args.apply:
                remove_tree(target)
                record["removed"] = not os.path.lexists(target)
        except (OSError, ValueError) as exc:
            record["error"] = str(exc)
            errors.append({"path": str(target), "error": str(exc)})
        records.append(record)
    print(
        json.dumps(
            {
                "schema": "facman.workspace_hygiene_legacy_cleanup.v1",
                "mode": "apply" if args.apply else "plan",
                "acknowledged_unowned": args.acknowledge_unowned,
                "result": "pass" if not errors else "partial",
                "summary": {
                    "target_count": len(records),
                    "removed_count": sum(bool(record["removed"]) for record in records),
                    "file_count": sum(int(record.get("files", 0)) for record in records),
                    "bytes": sum(int(record.get("bytes", 0)) for record in records),
                    "error_count": len(errors),
                },
                "errors": errors,
                "targets": records,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


def command_legacy_prune(args: argparse.Namespace) -> int:
    if args.apply and not args.acknowledge_unowned:
        raise ValueError("--apply requires --acknowledge-unowned")
    allowed = [Path(value).expanduser() for value in args.allowed_root]
    root = validate_legacy_path(
        Path(args.path).expanduser(),
        allowed,
        args.allow_filesystem_root,
        allow_shared_prunable_root=True,
    )
    preserved = {value.casefold() for value in args.preserve_child_name}
    existing = {child.name.casefold() for child in root.iterdir()}
    missing = sorted(preserved - existing)
    if missing:
        raise ValueError(
            "preserved direct child does not exist: " + ", ".join(missing)
        )
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        record: dict[str, Any] = {
            "path": str(child),
            "preserved": child.name.casefold() in preserved,
            "removed": False,
        }
        try:
            if is_reparse_or_link(child):
                raise ValueError(f"legacy child is a link or reparse point: {child}")
            if child.is_dir():
                files, size, links = directory_inventory(child)
                record.update(
                    {
                        "files": files,
                        "bytes": size,
                        "contained_reparse_points": [str(path) for path in links],
                    }
                )
                if args.apply and not record["preserved"]:
                    remove_tree(child)
            else:
                record.update({"files": 1, "bytes": child.stat().st_size})
                if args.apply and not record["preserved"]:
                    try:
                        child.unlink()
                    except PermissionError:
                        os.chmod(child, stat.S_IWRITE)
                        child.unlink()
            if args.apply and not record["preserved"]:
                record["removed"] = not os.path.lexists(child)
        except (OSError, ValueError) as exc:
            record["error"] = str(exc)
            errors.append({"path": str(child), "error": str(exc)})
        records.append(record)
    removable = [record for record in records if not record["preserved"]]
    payload = {
        "schema": "facman.workspace_hygiene_legacy_prune.v1",
        "mode": "apply" if args.apply else "plan",
        "result": "pass" if not errors else "partial",
        "root": str(root),
        "preserved_child_names": sorted(args.preserve_child_name),
        "summary": {
            "child_count": len(records),
            "preserved_count": len(records) - len(removable),
            "removable_count": len(removable),
            "removed_count": sum(bool(record["removed"]) for record in removable),
            "removable_bytes": sum(int(record.get("bytes", 0)) for record in removable),
            "error_count": len(errors),
        },
        "errors": errors,
        "children": records,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Plan and apply bounded FacMan workspace hygiene")
    commands = result.add_subparsers(dest="command", required=True)
    paths = commands.add_parser("paths", help="show the canonical portable development layout")
    paths.set_defaults(handler=command_paths)
    doctor = commands.add_parser("doctor", help="audit task roots, quotas, and Git worktrees")
    doctor.add_argument("--base", default="origin/main")
    doctor.add_argument("--measure", action="store_true")
    doctor.add_argument("--max-task-roots", type=int, default=development_layout.DEFAULT_MAX_TASK_ROOTS)
    doctor.add_argument("--max-worktrees", type=int, default=2)
    doctor.add_argument("--max-bytes", type=int, default=development_layout.DEFAULT_MAX_BYTES)
    doctor.set_defaults(handler=command_doctor)
    clean = commands.add_parser("clean", help="remove expired marker-owned task roots")
    clean.add_argument("--max-age-days", type=int, default=development_layout.DEFAULT_RETENTION_DAYS)
    clean.add_argument("--include-current", action="store_true")
    clean.add_argument("--apply", action="store_true")
    clean.set_defaults(handler=command_clean)
    worktrees = commands.add_parser("worktrees", help="remove clean worktrees contained in a base ref")
    worktrees.add_argument("--base", default="origin/main")
    worktrees.add_argument("--apply", action="store_true")
    worktrees.set_defaults(handler=command_worktrees)
    add = commands.add_parser(
        "worktree-add", help="create one task branch in the canonical worktree store"
    )
    add.add_argument("branch")
    add.add_argument("--start", default="origin/dev")
    add.add_argument("--cleanup-base", default="origin/main")
    add.add_argument("--max-worktrees", type=int, default=2)
    add.set_defaults(handler=command_worktree_add)
    legacy = commands.add_parser("legacy-clean", help="explicit one-time cleanup for unmarked old roots")
    legacy.add_argument("--path", action="append")
    legacy.add_argument("--allowed-root", action="append", required=True)
    legacy.add_argument("--discover-direct-children", action="store_true")
    legacy.add_argument("--exclude-name", action="append", default=[])
    legacy.add_argument("--allow-filesystem-root", action="store_true")
    legacy.add_argument("--acknowledge-unowned", action="store_true")
    legacy.add_argument("--apply", action="store_true")
    legacy.set_defaults(handler=command_legacy_clean)
    prune = commands.add_parser(
        "legacy-prune", help="remove direct children from one explicit old root"
    )
    prune.add_argument("--path", required=True)
    prune.add_argument("--allowed-root", action="append", required=True)
    prune.add_argument("--preserve-child-name", action="append", default=[])
    prune.add_argument("--allow-filesystem-root", action="store_true")
    prune.add_argument("--acknowledge-unowned", action="store_true")
    prune.add_argument("--apply", action="store_true")
    prune.set_defaults(handler=command_legacy_prune)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError) as exc:
        print(f"workspace-hygiene: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
