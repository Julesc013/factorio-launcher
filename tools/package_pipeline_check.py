# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    package_dir = ROOT / "tools/package"
    for name in ("profile", "staging", "components", "manifests", "platform_proof", "archive", "provenance", "verification"):
        if not (package_dir / f"{name}.py").is_file():
            problems.append(f"package module missing: {name}.py")
    wrapper = (ROOT / "tools/package_build.py").read_text(encoding="utf-8")
    if len(wrapper.splitlines()) > 20 or "tools.package.pipeline" not in wrapper:
        problems.append("package_build.py is not a small compatibility CLI wrapper")
    pipeline = (package_dir / "pipeline.py").read_text(encoding="utf-8")
    for anchor in ("package_staging.install_tree(", "package_archive.write(", "package_provenance.require_clean("):
        if anchor not in pipeline:
            problems.append(f"package pipeline integration missing: {anchor}")
    if "shutil.make_archive(" in pipeline:
        problems.append("package pipeline retains nondeterministic shutil archive creation")
    resolve = pipeline.split("def resolve_source_target", 1)[1].split("def pinned_source_revisions", 1)[0]
    if ".rglob(" in resolve:
        problems.append("package pipeline recursively searches build outputs")
    for profile_id in ("windows_portable_cli_x64", "linux_portable_cli_x64", "macos_portable_cli_x64"):
        with (ROOT / "release/profiles" / profile_id / "profile.toml").open("rb") as handle:
            profile = tomllib.load(handle)
        proof = profile.get("proof", {})
        for field in ("runner", "architecture", "deployment_target", "libc_baseline", "package_format"):
            if not proof.get(field):
                problems.append(f"{profile_id}: proof.{field} is required")
    if '"source_revision": revisions["factorio_launcher"]' not in pipeline:
        problems.append("current source revision is not recorded independently")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"package-pipeline-check: {problem}", file=sys.stderr)
        return 1
    print("package-pipeline-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
