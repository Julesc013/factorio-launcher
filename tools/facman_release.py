# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_compiler.canonical import pretty_json
from tools.release_compiler.compiler import (
    OUTPUT_FILES,
    ResolutionFailure,
    diff_resolutions,
    explain,
    load_inputs,
    resolve,
)
from tools.release_compiler.outputs import load_resolution, validate_resolution, write_resolution
from tools.release_compiler.packages import inspect_package, verify_package
from tools.release_compiler.staging import parse_source_overrides, stage, verify_stage


DEFAULT_INPUT = ROOT / "release" / "index"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facman-release",
        description="Resolve and inspect deterministic FacMan product compositions.",
    )
    parser.add_argument(
        "--input-root",
        default=str(DEFAULT_INPUT),
        help="directory containing the reviewed release model inputs",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate authored inputs or a resolved graph")
    validate.add_argument("--resolution", help="existing resolution directory to validate")

    resolve_parser = commands.add_parser("resolve", help="resolve one exact target graph")
    resolve_parser.add_argument("--target", required=True)
    resolve_parser.add_argument("--output", required=True)

    explain_parser = commands.add_parser("explain", help="explain component selection or exclusion")
    explain_parser.add_argument("--target", required=True)
    explain_parser.add_argument("--component")

    diff_parser = commands.add_parser("diff", help="compare two resolved graph directories")
    diff_parser.add_argument("left")
    diff_parser.add_argument("right")

    stage_parser = commands.add_parser("stage", help="materialize one canonical staged image")
    stage_parser.add_argument("--resolution", required=True)
    stage_parser.add_argument("--artifact", required=True)
    stage_parser.add_argument("--source-root", required=True)
    stage_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="explicit build source override in NAME=PATH form",
    )
    stage_parser.add_argument("--output", required=True)

    verify_stage_parser = commands.add_parser(
        "verify-stage",
        help="verify a staged image against one resolved artifact graph",
    )
    verify_stage_parser.add_argument("--resolution", required=True)
    verify_stage_parser.add_argument("--artifact", required=True)
    verify_stage_parser.add_argument("--stage", required=True)

    inspect_parser = commands.add_parser(
        "inspect-package",
        help="inspect a package directory or archive without extracting it",
    )
    inspect_parser.add_argument("--package", required=True)
    inspect_parser.add_argument("--output")

    verify_package_parser = commands.add_parser(
        "verify-package",
        help="verify a package is an exact projection of a resolved staged graph",
    )
    verify_package_parser.add_argument("--resolution", required=True)
    verify_package_parser.add_argument("--artifact", required=True)
    verify_package_parser.add_argument("--package", required=True)

    return parser


def _inputs(args: argparse.Namespace):
    return load_inputs(Path(args.input_root), ROOT)


def _resolve(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    return resolve(_inputs(args), str(args.target))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            if args.resolution:
                outputs = load_resolution(Path(args.resolution))
                validate_resolution(outputs, ROOT)
                print(f"facman-release: valid resolution {outputs['composition']['resolution_digest']}")
            else:
                inputs = _inputs(args)
                print(f"facman-release: valid inputs ({len(inputs.input_hashes)} files)")
            return 0
        if args.command == "resolve":
            outputs = _resolve(args)
            validate_resolution(outputs, ROOT)
            destination = write_resolution(Path(args.output), outputs)
            print(
                "facman-release: resolved "
                f"{args.target} {outputs['composition']['resolution_digest']} -> {destination}"
            )
            return 0
        if args.command == "explain":
            print(pretty_json(explain(_resolve(args), args.component)), end="")
            return 0
        if args.command == "diff":
            left = load_resolution(Path(args.left))
            right = load_resolution(Path(args.right))
            value = diff_resolutions(left["components"] | left["paths"], right["components"] | right["paths"])
            value["left_digest"] = left["composition"]["resolution_digest"]
            value["right_digest"] = right["composition"]["resolution_digest"]
            print(pretty_json(value), end="")
            return 0
        if args.command == "stage":
            destination = stage(
                Path(args.resolution),
                str(args.artifact),
                Path(args.source_root),
                parse_source_overrides(list(args.source)),
                Path(args.output),
            )
            print(f"facman-release: staged {args.artifact} -> {destination}")
            return 0
        if args.command == "verify-stage":
            print(
                pretty_json(
                    verify_stage(
                        Path(args.resolution),
                        str(args.artifact),
                        Path(args.stage),
                    )
                ),
                end="",
            )
            return 0
        if args.command == "inspect-package":
            inspection = inspect_package(Path(args.package))
            rendered = pretty_json(inspection)
            if args.output:
                output = Path(args.output)
                if output.exists():
                    raise ValueError(f"inspection output already exists: {output}")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(f"facman-release: inspected {args.package} -> {output}")
            else:
                print(rendered, end="")
            return 0
        if args.command == "verify-package":
            print(
                pretty_json(
                    verify_package(
                        Path(args.resolution),
                        str(args.artifact),
                        Path(args.package),
                    )
                ),
                end="",
            )
            return 0
        raise AssertionError(f"unhandled command {args.command}")
    except ResolutionFailure as exc:
        failure = {
            "schema": "facman.release_resolution_failure.v1",
            "diagnostics": exc.diagnostics,
            "minimal_conflict_sets": [item.get("constraints", []) for item in exc.diagnostics],
        }
        print(pretty_json(failure), file=sys.stderr, end="")
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"facman-release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
