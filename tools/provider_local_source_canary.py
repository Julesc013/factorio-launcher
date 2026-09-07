# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Run a disposable source-static FacMan canary, leaving all stable pins intact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import provider_canary_process as bounded  # noqa: E402
from tools import provider_conformance as inputs  # noqa: E402
from tools import provider_local_source_custody as custody  # noqa: E402
from tools import provider_package_manifest_import as importer  # noqa: E402
from tools import provider_sdk_consumption as consumption  # noqa: E402
from tools import provider_semantic_conformance as semantics  # noqa: E402

CTESTS = ("flb_setup_gateway_smoke", "flb_factorio_setup_recipe_smoke",
          "fl_transaction_session_smoke", "fl_archive_core_smoke")
STABLE_PATHS = tuple("release/index/" + name for name in importer.INDEX_FILENAMES)


def write_json(path: Path, value: dict) -> None:
    bounded.write_json(path, value)


def consumer_source() -> dict:
    changed = set(custody.git(ROOT, "diff", "HEAD", "--name-only").splitlines())
    changed.update(custody.git(ROOT, "ls-files", "--others", "--exclude-standard").splitlines())
    return {"head": custody.git(ROOT, "rev-parse", "HEAD"),
            "base_tree": custody.git(ROOT, "rev-parse", "HEAD^{tree}"),
            "status": custody.git(ROOT, "status", "--porcelain=v1"),
            "changed_files": {name: custody.sha256(ROOT / name) if (ROOT / name).is_file() else None
                              for name in sorted(changed)}}


class CanaryRunner:
    """Canary-only adapter; the general provider conformance runner is unchanged."""

    def __init__(self, output_dir: Path, budget: bounded.Budget) -> None:
        self.output_dir, self.budget, self.counter = output_dir, budget, 0
        output_dir.mkdir()

    def run(self, label, command, cwd, *, environment=None, expect_failure=False):
        self.counter += 1
        env = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
        env.update(environment or {})
        result = bounded.command(list(command), cwd=cwd, environment=env, timeout=30,
            budget=self.budget, directory=self.output_dir / f"{self.counter:03d}")
        if result.receipt["termination"] != "completed" or (result.returncode == 0) == expect_failure:
            raise bounded.CommandFailure(result)
        return inputs.CommandResult(result.returncode, result.stdout.decode("utf-8"),
                                    str(result.directory / "receipt.json"))


def read_result(path: Path) -> tuple[dict, str]:
    # A worker's partial observation never confers the supervisor's successful outcome.
    custody.provider_source_bytes.reject_indirection(path)
    with path.open("rb") as stream:
        raw = stream.read(bounded.MAX_RECEIPT_BYTES + 1)
    if len(raw) > bounded.MAX_RECEIPT_BYTES:
        raise ValueError("canary worker result exceeds its 8 MiB observation limit")
    value = json.loads(raw, object_pairs_hook=custody._pairs)
    if not isinstance(value, dict):
        raise ValueError("canary worker result must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def execute(args: argparse.Namespace) -> dict:
    """Supervise the entire worker, including source reads and final observations."""
    overall = bounded.seconds(getattr(args, "overall_timeout", 1800), "overall deadline")
    limit = bounded.seconds(getattr(args, "command_timeout", 900), "command deadline")
    if os.name != "nt":
        raise ValueError("local canary deadline containment is qualified on Windows only")
    work = args.work_dir.resolve()
    control = work.parent / (work.name + "-control")
    roots = (ROOT.resolve(), args.usk_root.resolve(), args.ulk_root.resolve())
    for path in (work, control, args.temp_root.resolve(strict=True)):
        if any(path.is_relative_to(root) or root.is_relative_to(path) for root in roots):
            raise ValueError("canary work/control/temp paths must remain outside source roots")
    if work.exists() or control.exists():
        raise ValueError("canary work and control roots must both be new")
    control.mkdir()
    commands = control / "commands"
    commands.mkdir()
    environment = dict(os.environ, TEMP=str(args.temp_root), TMP=str(args.temp_root),
        PYTHONDONTWRITEBYTECODE="1", FACMAN_CANARY_OWNED_JOB="1",
        FACMAN_CANARY_EVIDENCE_ROOT=str(commands))
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--overall-timeout", str(overall), "--command-timeout", str(limit)]
    for name in ("usk_root", "ulk_root", "work_dir", "temp_root", "review_receipt",
                 "review_sha256", "usk_commit", "usk_tree", "usk_ref"):
        command += ["--" + name.replace("_", "-"), str(getattr(args, name))]
    budget = bounded.Budget(overall, overall)
    result = bounded.command(command, cwd=ROOT, environment=environment, timeout=overall,
                             budget=budget, directory=control / "worker")
    final = {"schema": "facman.canary-supervision.v1", "result": "failed_retained",
             "work_dir": str(work), "worker_receipt": str(result.directory / "receipt.json"),
             "worker_termination": result.receipt["termination"],
             "overall_seconds": overall, "command_seconds": limit,
             "authority": dict(inputs.AUTHORITY)}
    try:
        bounded.require(result)
        observation, observation_hash = read_result(work / "evidence/observation.json")
        if (observation.get("schema") != "facman.provider_local_source_canary.v1" or
                observation.get("result") != "source_static_consumer_pass" or
                observation.get("stable_inputs_unchanged") is not True or
                observation.get("consumer_source_unchanged") is not True or
                observation.get("authority") != dict(inputs.AUTHORITY)):
            raise ValueError("canary worker did not return a complete successful observation")
        if budget.remaining() <= 0:
            raise ValueError("overall deadline expired during bounded result collection")
        final["result"] = "supervised_source_static_consumer_pass"
        final["observation_sha256"] = observation_hash
        return observation
    except (ValueError, OSError, RuntimeError) as error:
        final["error"] = str(error)[:4096]
        raise
    finally:
        write_json(control / "supervision.json", final)


def _execute_worker(args: argparse.Namespace) -> dict:
    budget = bounded.Budget(args.overall_timeout, args.command_timeout)
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
        print(name, flush=True)
        result = bounded.command(command, cwd=ROOT, environment=environment,
            timeout=args.command_timeout, budget=budget, directory=evidence / name)
        receipt["steps"].append({"name": name, "command": command,
            "exit_code": result.returncode, "termination": result.receipt["termination"],
            "seconds": result.receipt["elapsed_seconds"],
            "receipt": str(result.directory / "receipt.json"),
            "sha256": custody.sha256(result.directory / "receipt.json")})
        write_json(evidence / "observation.json", receipt)
        bounded.require(result)

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
                                      CanaryRunner(evidence / "ulk-source", budget))
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
                    f"-DFACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_SHA256={local_hash}",
                    "-DFACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_TIMEOUT=45"]
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
                "--fixture-root", str(temp / (work.name + "-" + compression)),
                "--canary-command-timeout", str(args.command_timeout)])
        receipt["executables"] = [{"path": path.relative_to(build).as_posix(),
                                    "sha256": custody.sha256(path)}
                                   for path in sorted(build.rglob("*.exe"))]
        custody.validate(local_path, local_hash, args.usk_root, args.usk_commit,
                         args.usk_tree, custody.REMOTE, args.usk_ref)
        inputs.observe_provider(specs["universal_launcher"], args.ulk_root,
                                CanaryRunner(evidence / "ulk-source-after", budget))
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
    parser.add_argument("--overall-timeout", type=float, default=1800)
    parser.add_argument("--command-timeout", type=float, default=900)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        result = _execute_worker(args) if args.worker else execute(args)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"local-source-canary: {error}", file=sys.stderr)
        return 1
    print(result["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
