from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from factorio_launcher.binding.product_manifest import load_product_manifest
from factorio_launcher.core.config import APP_VERSION, default_workspace
from factorio_launcher.core.workspace import (
    ensure_workspace,
    list_install_refs,
    list_instances,
    load_install_ref,
    load_instance,
    save_install_ref,
)
from factorio_launcher.diagnostics.doctor import run_doctor
from factorio_launcher.discovery.detect_install import inspect_install, scan_common_installs
from factorio_launcher.instances.instance_create import create_instance
from factorio_launcher.launch.launch_plan_builder import build_launch_plan
from factorio_launcher.launch.process_runner import run_launch_plan


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        print(f"FacMan {APP_VERSION}")
        return 0
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facman",
        description="Unofficial Factorio launcher and isolated instance manager.",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=default_workspace(),
        help="workspace root (default: FACMAN_WORKSPACE, FACTORIO_LAUNCHER_WORKSPACE, or user profile)",
    )
    subparsers = parser.add_subparsers(dest="command")

    product = subparsers.add_parser("product", help="product binding commands")
    product_sub = product.add_subparsers(dest="product_command", required=True)
    product_inspect = product_sub.add_parser("inspect", help="inspect the Factorio product manifest")
    product_inspect.add_argument("--json", action="store_true", help="emit JSON")
    product_inspect.set_defaults(handler=handle_product_inspect)

    doctor = subparsers.add_parser("doctor", help="run diagnostics")
    doctor.add_argument("scope", nargs="?", choices=["instance", "install", "modset"])
    doctor.add_argument("id", nargs="?")
    doctor.add_argument("--json", action="store_true", help="emit JSON")
    doctor.set_defaults(handler=handle_doctor)

    installs = subparsers.add_parser("installs", help="install discovery and registration")
    installs_sub = installs.add_subparsers(dest="installs_command", required=True)
    installs_scan = installs_sub.add_parser("scan", help="scan common install locations")
    installs_scan.add_argument("--json", action="store_true", help="emit JSON")
    installs_scan.add_argument("--register", action="store_true", help="register discovered installs")
    installs_scan.set_defaults(handler=handle_installs_scan)
    installs_list = installs_sub.add_parser("list", help="list registered install references")
    installs_list.add_argument("--json", action="store_true", help="emit JSON")
    installs_list.set_defaults(handler=handle_installs_list)
    installs_inspect = installs_sub.add_parser("inspect", help="inspect a registered install")
    installs_inspect.add_argument("install_id")
    installs_inspect.add_argument("--json", action="store_true", help="emit JSON")
    installs_inspect.set_defaults(handler=handle_installs_inspect)
    installs_import = installs_sub.add_parser("import", help="register a manual install path")
    installs_import.add_argument("path", type=Path)
    installs_import.add_argument("--id", dest="install_id")
    installs_import.add_argument("--source", choices=["manual", "portable", "headless", "steam"], default="manual")
    installs_import.add_argument("--json", action="store_true", help="emit JSON")
    installs_import.set_defaults(handler=handle_installs_import)

    instances = subparsers.add_parser("instances", help="isolated instance commands")
    instances_sub = instances.add_subparsers(dest="instances_command", required=True)
    instances_create = instances_sub.add_parser("create", help="create an isolated instance")
    instances_create.add_argument("name")
    instances_create.add_argument("--install", required=True, dest="install_id")
    instances_create.add_argument("--template", default="vanilla")
    instances_create.add_argument("--id", dest="instance_id")
    instances_create.add_argument("--json", action="store_true", help="emit JSON")
    instances_create.set_defaults(handler=handle_instances_create)
    instances_list = instances_sub.add_parser("list", help="list instances")
    instances_list.add_argument("--json", action="store_true", help="emit JSON")
    instances_list.set_defaults(handler=handle_instances_list)
    instances_inspect = instances_sub.add_parser("inspect", help="inspect an instance")
    instances_inspect.add_argument("instance_id")
    instances_inspect.add_argument("--json", action="store_true", help="emit JSON")
    instances_inspect.set_defaults(handler=handle_instances_inspect)

    launch_plan = subparsers.add_parser("launch-plan", help="build a dry-run launch plan")
    launch_plan.add_argument("instance_id")
    launch_plan.add_argument("--profile")
    launch_plan.add_argument("--json", action="store_true", help="emit JSON")
    launch_plan.set_defaults(handler=handle_launch_plan)

    run = subparsers.add_parser("run", help="dry-run or execute an instance launch")
    run.add_argument("instance_id")
    run.add_argument("--profile")
    run.add_argument("--execute", action="store_true", help="execute after building the launch plan")
    run.add_argument("--json", action="store_true", help="emit JSON launch plan")
    run.set_defaults(handler=handle_run)

    return parser


def handle_product_inspect(args: argparse.Namespace) -> int:
    manifest = load_product_manifest()
    if args.json:
        print_json(manifest)
    else:
        print(f"Product: {manifest['display_name']}")
        print(f"Public name: {manifest['public_name']}")
        print(f"Binding: {manifest['binding']}")
        print("Capabilities:")
        for capability in manifest["capabilities"]:
            print(f"  - {capability}")
        print("Boundaries:")
        for key, value in manifest.get("boundaries", {}).items():
            print(f"  - {key}: {value}")
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    if args.scope == "install":
        if not args.id:
            raise ValueError("doctor install requires an install id")
        report = doctor_install(args.workspace, args.id)
    elif args.scope == "instance":
        if not args.id:
            raise ValueError("doctor instance requires an instance id")
        report = doctor_instance(args.workspace, args.id)
    elif args.scope == "modset":
        report = {
            "status": "warning",
            "problems": [],
            "warnings": ["modset verification is planned for v0.4"],
            "suggested_fixes": ["use local ZIP mods only until modset locking lands"],
        }
    else:
        report = run_doctor(args.workspace)
    if args.json:
        print_json(report)
    else:
        print_report(report)
    return 1 if report.get("status") == "blocked" else 0


def doctor_install(workspace: Path, install_id: str) -> dict[str, Any]:
    install_ref = load_install_ref(workspace, install_id)
    problems = list(install_ref.get("verification", {}).get("problems", []))
    executable = Path(str(install_ref.get("executable", "")))
    if not executable.is_file():
        problems.append("registered executable no longer exists")
    status = "blocked" if problems else "ok"
    return {
        "status": status,
        "install_id": install_id,
        "ownership": install_ref["ownership"],
        "problems": problems,
        "warnings": [],
        "suggested_fixes": ["re-run installs import with the correct path"] if problems else [],
    }


def doctor_instance(workspace: Path, instance_id: str) -> dict[str, Any]:
    instance = load_instance(workspace, instance_id)
    root = Path(str(instance["local_data_root"]))
    problems = []
    for rel in ["config", "mods", "saves", "logs", "locks"]:
        if not (root / rel).is_dir():
            problems.append(f"missing instance directory: {rel}")
    status = "blocked" if problems else "ok"
    return {
        "status": status,
        "instance_id": instance_id,
        "local_data_root": str(root),
        "problems": problems,
        "warnings": [],
        "suggested_fixes": ["recreate the instance or restore missing folders"] if problems else [],
    }


def handle_installs_scan(args: argparse.Namespace) -> int:
    ensure_workspace(args.workspace)
    installs = scan_common_installs()
    if args.register:
        for install_ref in installs:
            save_install_ref(args.workspace, install_ref)
    if args.json:
        print_json(installs)
    elif not installs:
        print("No Factorio installs found in common locations.")
    else:
        for install_ref in installs:
            suffix = " registered" if args.register else ""
            print(f"{install_ref['install_id']} {install_ref['version'] or 'unknown'} {install_ref['ownership']}{suffix}")
    return 0


def handle_installs_list(args: argparse.Namespace) -> int:
    installs = list_install_refs(args.workspace)
    if args.json:
        print_json(installs)
    elif not installs:
        print("No registered install references.")
    else:
        for install_ref in installs:
            print(
                f"{install_ref['install_id']} "
                f"{install_ref.get('version') or 'unknown'} "
                f"{install_ref['ownership']} "
                f"{install_ref['executable']}"
            )
    return 0


def handle_installs_inspect(args: argparse.Namespace) -> int:
    install_ref = load_install_ref(args.workspace, args.install_id)
    if args.json:
        print_json(install_ref)
    else:
        print_install_ref(install_ref)
    return 0


def handle_installs_import(args: argparse.Namespace) -> int:
    install_ref = inspect_install(args.path, source=args.source, install_id=args.install_id)
    if install_ref["verification"]["status"] == "invalid":
        problems = "; ".join(install_ref["verification"]["problems"])
        raise ValueError(f"invalid Factorio install: {problems}")
    save_install_ref(args.workspace, install_ref)
    if args.json:
        print_json(install_ref)
    else:
        print(f"Registered {install_ref['install_id']} ({install_ref['ownership']})")
        print(f"Executable: {install_ref['executable']}")
    return 0


def handle_instances_create(args: argparse.Namespace) -> int:
    instance = create_instance(
        args.workspace,
        name=args.name,
        install_id=args.install_id,
        template_id=args.template,
        instance_id=args.instance_id,
    )
    if args.json:
        print_json(instance)
    else:
        print(f"Created instance {instance['instance_id']}")
        print(f"Data root: {instance['local_data_root']}")
    return 0


def handle_instances_list(args: argparse.Namespace) -> int:
    instances = list_instances(args.workspace)
    if args.json:
        print_json(instances)
    elif not instances:
        print("No instances.")
    else:
        for instance in instances:
            print(f"{instance['instance_id']} {instance['profile']} {instance['local_data_root']}")
    return 0


def handle_instances_inspect(args: argparse.Namespace) -> int:
    instance = load_instance(args.workspace, args.instance_id)
    if args.json:
        print_json(instance)
    else:
        print(f"Instance: {instance['instance_id']}")
        print(f"Display name: {instance['display_name']}")
        print(f"Install ref: {instance['install_ref']}")
        print(f"Data root: {instance['local_data_root']}")
        print(f"Profile: {instance['profile']}")
    return 0


def handle_launch_plan(args: argparse.Namespace) -> int:
    plan = build_launch_plan(args.workspace, args.instance_id, profile_id=args.profile)
    if args.json:
        print_json(plan)
    else:
        print_launch_plan(plan)
    return 0


def handle_run(args: argparse.Namespace) -> int:
    plan = build_launch_plan(args.workspace, args.instance_id, profile_id=args.profile)
    if args.json:
        print_json(plan)
    else:
        print_launch_plan(plan)
    if not args.execute:
        print("Dry-run only. Re-run with --execute to launch Factorio.")
        return 0
    return run_launch_plan(plan)


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def print_report(report: dict[str, Any]) -> None:
    print(f"Status: {report['status']}")
    if "workspace" in report:
        print(f"Workspace: {report['workspace']}")
    if "registered_installs" in report:
        print(f"Registered installs: {report['registered_installs']}")
    if "instances" in report:
        print(f"Instances: {report['instances']}")
    for label in ["problems", "warnings", "suggested_fixes"]:
        values = report.get(label, [])
        if values:
            print(f"{label.replace('_', ' ').title()}:")
            for value in values:
                print(f"  - {value}")
    if "setup_integration" in report:
        print(f"Setup integration: {report['setup_integration']}")


def print_install_ref(install_ref: dict[str, Any]) -> None:
    print(f"Install: {install_ref['install_id']}")
    print(f"Source: {install_ref['source']}")
    print(f"Ownership: {install_ref['ownership']}")
    print(f"Version: {install_ref.get('version') or 'unknown'}")
    print(f"Platform: {install_ref['platform']}")
    print(f"Executable: {install_ref['executable']}")
    print(f"App dir: {install_ref['app_dir']}")
    print(f"Verification: {install_ref['verification'].get('status')}")
    problems = install_ref["verification"].get("problems", [])
    if problems:
        print("Problems:")
        for problem in problems:
            print(f"  - {problem}")


def print_launch_plan(plan: dict[str, Any]) -> None:
    print(f"Instance: {plan['instance_id']}")
    print(f"Profile: {plan['profile_id']}")
    print(f"Executable: {plan['executable']}")
    print("Args:")
    for arg in plan["args"]:
        print(f"  {arg}")
    print("Preflight:")
    for check in plan["preflight"]:
        print(f"  - {check}")
