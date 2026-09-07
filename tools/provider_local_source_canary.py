# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Run a disposable source-static FacMan canary, leaving all stable pins intact."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_conformance as inputs  # noqa: E402
from tools import provider_local_source_custody as custody  # noqa: E402
from tools import provider_package_manifest_import as importer  # noqa: E402
from tools import provider_sdk_consumption as consumption  # noqa: E402
from tools import provider_semantic_conformance as semantics  # noqa: E402

CTESTS = ("flb_setup_gateway_smoke", "flb_factorio_setup_recipe_smoke",
          "fl_transaction_session_smoke", "fl_archive_core_smoke")
STABLE_PATHS = tuple("release/index/" + name for name in importer.INDEX_FILENAMES)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def consumer_source() -> dict:
    changed = set(custody.git(ROOT, "diff", "HEAD", "--name-only").splitlines())
    changed.update(custody.git(ROOT, "ls-files", "--others", "--exclude-standard").splitlines())
    return {"head": custody.git(ROOT, "rev-parse", "HEAD"),
            "base_tree": custody.git(ROOT, "rev-parse", "HEAD^{tree}"),
            "status": custody.git(ROOT, "status", "--porcelain=v1"),
            "changed_files": {name: custody.sha256(ROOT / name) if (ROOT / name).is_file() else None
                              for name in sorted(changed)}}


def execute(args: argparse.Namespace) -> dict:
    roots = [ROOT.resolve(), args.usk_root.resolve(), args.ulk_root.resolve()]
    work = args.work_dir.resolve()
    temp = args.temp_root.resolve(strict=True)
    for root in roots:
        if work.is_relative_to(root) or root.is_relative_to(work) or temp.is_relative_to(root):
            raise ValueError("canary work and temporary directories must be outside source roots")
    if work.exists() or not temp.is_dir():
        raise ValueError("canary work directory must be new; temporary root must exist")
    before = {name: custody.sha256(ROOT / name) for name in STABLE_PATHS}
    if custody.sha256(args.review_receipt) != args.review_sha256:
        raise ValueError("operator-selected review receipt digest differs")
    work.mkdir(parents=False)
    evidence = work / "evidence"
    evidence.mkdir()
    receipt = {
        "schema": "facman.provider_local_source_canary.v1", "result": "running",
        "source_consumption_only": True, "authority": dict(inputs.AUTHORITY),
        "stable_inputs_before": before, "consumer_source_before": consumer_source(),
        "steps": [], "pending": [
            "installed_static_shared_and_relocated", "consumer_interruption_replay",
            "protected_commit_authority", "generation_and_retained_cleanup",
            "provider_adoption", "release_qualification"],
    }
    environment = dict(os.environ, TEMP=str(temp), TMP=str(temp), PYTHONDONTWRITEBYTECODE="1",
                       FACMAN_PROVIDER_CANARY_KEEP_FIXTURES="1")

    def run(name: str, command: list[str]) -> None:
        log = evidence / (name + ".log")
        start = time.monotonic()
        print(name, flush=True)
        with log.open("xb") as output:
            result = subprocess.run(command, cwd=ROOT, env=environment,
                                    stdout=output, stderr=subprocess.STDOUT, check=False)
        receipt["steps"].append({"name": name, "command": command,
                                 "exit_code": result.returncode,
                                 "seconds": round(time.monotonic() - start, 3),
                                 "log": log.name, "sha256": custody.sha256(log)})
        write_json(evidence / "observation.json", receipt)
        if result.returncode:
            raise ValueError(f"{name} failed; raw log and fixtures retained at {work}")

    try:
        local = {
            "schema": "facman.provider_local_source_custody.v1",
            "scope": "source_static_sdk_candidate_only",
            "source": {"commit": args.usk_commit, "tree": args.usk_tree,
                       "ref": args.usk_ref, "remote": custody.REMOTE,
                       "repository": "Julesc013/universal-setup"},
            "review": {"receipt": str(args.review_receipt.resolve()),
                       "sha256": args.review_sha256},
            "authority": {"provider_adoption": False, "publication": False,
                          "stable_identity": False, "release_eligible": False},
        }
        local_path = work / "local-source-custody.json"
        write_json(local_path, local)
        local_hash = custody.sha256(local_path)
        custody.validate(local_path, local_hash, args.usk_root, args.usk_commit,
                         args.usk_tree, custody.REMOTE, args.usk_ref)
        specs = {item.provider_id: item for item in inputs.PROVIDERS}
        ulk = inputs.observe_provider(specs["universal_launcher"], args.ulk_root,
                                      inputs.CommandRunner(evidence / "ulk-source"))
        usk = inputs.ProviderSource(specs["universal_setup"], args.usk_root,
                                    args.usk_commit, args.usk_tree)
        sources = {"universal_launcher": ulk, "universal_setup": usk}
        tracked = tomllib.loads((ROOT / "release/index/workspace_lock.v1.toml").read_text())
        selected = {row["id"]: row for row in tracked["component"] if row["id"] in sources}
        lock = tomllib.loads(inputs.candidate_lock_text(
            list(sources.values()), selected, candidate_class="sdk_consumption"))
        for row in lock["component"]:
            if row["id"] == "universal_setup":
                row["required_ref"] = args.usk_ref
        lock_path = work / "candidate-lock.toml"
        lock_path.write_bytes(importer.render_toml(lock))
        build = work / "native"
        command = consumption._candidate_command(
            ROOT, build, lock_path, semantics.MODES[0], sources, None, None,
            "cmake", "Release", "x64")
        command = [value for value in command if value != "-DFACMAN_BUILD_SELF_SETUP=OFF"]
        command += ["-G", "Visual Studio 18 2026", "-DFACMAN_BUILD_SELF_SETUP=ON",
                    f"-DPython3_EXECUTABLE={sys.executable}",
                    f"-DFACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE={local_path}",
                    f"-DFACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256={local_hash}"]
        receipt["providers"] = {key: {"commit": value.commit, "tree": value.tree}
                                for key, value in sources.items()}
        receipt["custody"] = {"path": str(local_path), "sha256": local_hash}
        receipt["candidate_lock_sha256"] = custody.sha256(lock_path)
        receipt["physical_source_observations"] = []

        def observe_boundary(name: str) -> None:
            physical: dict = {}
            custody.validate(local_path, local_hash, args.usk_root, args.usk_commit,
                             args.usk_tree, custody.REMOTE, args.usk_ref, observation=physical)
            previous = receipt["physical_source_observations"]
            if previous and physical != previous[0]["observation"]:
                raise ValueError("physical provider source changed between canary boundaries")
            previous.append({"boundary": name, "observation": physical})

        observe_boundary("before_configure")
        run("configure", command)
        observe_boundary("before_build")
        run("build", ["cmake", "--build", str(build), "--config", "Release", "--parallel", "4",
                      "--target", "facman_cli", "facman_setup", *CTESTS])
        observe_boundary("after_build")
        identity = build / "facman-build-identity.v1.txt"
        values = dict(segment.split("=", 1) for segment in identity.read_text().strip().split(";"))
        for key, expected in {"provider_lock_kind": "sdk_candidate",
                              "provider_conformance_only": "false",
                              "provider_sdk_consumption_candidate": "true",
                              "provider_candidate_differs_from_tracked": "true",
                              "provider_release_identity_coherent": "false"}.items():
            if values.get(key) != expected:
                raise ValueError(f"actual build identity misclassifies {key}")
        receipt["build_identity"] = {"value": values, "sha256": custody.sha256(identity)}
        run("native", ["ctest", "--test-dir", str(build), "-C", "Release",
                       "--output-on-failure", "-R", "^(" + "|".join(CTESTS) + ")$"])
        executables = sorted(build.rglob("FacManSetup.exe"))
        if len(executables) != 1:
            raise ValueError("canary must select exactly one actual FacManSetup executable")
        for compression in ("stored", "deflate"):
            run("self-setup-" + compression, [sys.executable,
                str(ROOT / "tests/integration/facman_self_setup_lifecycle.py"),
                "--setup-exe", str(executables[0]), "--compression", compression,
                "--fixture-root", str(temp / (work.name + "-" + compression))])
        receipt["executables"] = [{"path": path.relative_to(build).as_posix(),
                                    "sha256": custody.sha256(path)}
                                   for path in sorted(build.rglob("*.exe"))]
        custody.validate(local_path, local_hash, args.usk_root, args.usk_commit,
                         args.usk_tree, custody.REMOTE, args.usk_ref)
        inputs.observe_provider(specs["universal_launcher"], args.ulk_root,
                                inputs.CommandRunner(evidence / "ulk-source-after"))
        observe_boundary("after_tests")
        receipt["result"] = "source_static_consumer_pass"
    except (ValueError, OSError, RuntimeError) as error:
        receipt["result"] = "failed_retained"
        receipt["error"] = str(error)
        raise
    finally:
        receipt["consumer_source_after"] = consumer_source()
        receipt["consumer_source_unchanged"] = receipt["consumer_source_after"] == receipt["consumer_source_before"]
        receipt["stable_inputs_after"] = {name: custody.sha256(ROOT / name) for name in STABLE_PATHS}
        receipt["stable_inputs_unchanged"] = receipt["stable_inputs_after"] == before
        if not receipt["stable_inputs_unchanged"] or not receipt["consumer_source_unchanged"]:
            receipt["result"] = "failed_stable_input_changed"
        write_json(evidence / "observation.json", receipt)
    if not receipt["stable_inputs_unchanged"] or not receipt["consumer_source_unchanged"]:
        raise ValueError("stable release inputs changed during local canary")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("usk-root", "ulk-root", "work-dir", "temp-root", "review-receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("review-sha256", "usk-commit", "usk-tree", "usk-ref"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        result = execute(args)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"local-source-canary: {error}", file=sys.stderr)
        return 1
    print(result["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
