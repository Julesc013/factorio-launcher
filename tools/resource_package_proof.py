#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Qualify resource behavior of a supplied package; retain every private proof effect."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import development_layout, json_contract
from tools import resource_package_cases as cases

SCHEMA = ROOT / "contracts/schema/release/facman_resource_package_proof.v1.schema.json"
LOG_LIMIT = 8 * 1024 * 1024
COMMAND_TIMEOUT = 30
PROOF_TIMEOUT = 600
MAX_SOURCE = 4 * 1024 * 1024
SOURCE_FILES = ("tools/resource_package_proof.py", "tools/resource_package_cases.py",
                "tools/development_layout.py", "tools/json_contract.py",
                "contracts/schema/release/facman_resource_package_proof.v1.schema.json")


def source_identity() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                              timeout=15, text=True, encoding="utf-8").stdout.strip()
    return {"source_revision": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}"),
            "source_dirty": bool(git("status", "--porcelain", "--untracked-files=all"))}


def prepare(evidence: Path, package_root: Path) -> tuple[Path, dict]:
    evidence = cases.plain_path(evidence)
    cases.require(0 < len(evidence.stem) <= 96 and len(evidence.stem.encode("utf-8")) <= 192,
                  "evidence filename stem budget")
    cases.require(not evidence.exists(), "evidence destination already exists")
    for source in (ROOT.absolute(), package_root.absolute()):
        cases.require(not evidence.is_relative_to(source) and not source.is_relative_to(evidence),
                      "proof evidence overlaps package/source")
    owner = None
    for parent in evidence.parents:
        marker = parent / development_layout.MARKER_NAME
        if marker.exists():
            identity, data = cases.file_bytes(marker, 65536)
            marker_payload = development_layout.validate_marker_payload(parent, json.loads(data), ROOT)
            canonical_root = marker_payload.get("canonical_path")
            owner = {"root": canonical_root if isinstance(canonical_root, str) else str(parent.resolve()),
                     "marker_sha256": identity["sha256"]}
            break
    cases.require(owner is not None, "evidence requires a valid marker-owned task-root ancestor")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    work = evidence.parent / (evidence.stem + "-" + uuid.uuid4().hex[:12])
    work.mkdir()
    return work, owner


class Driver:
    def __init__(self, work: Path, receipt: dict, evidence_parent: Path) -> None:
        self.work, self.receipt, self.evidence_parent = work, receipt, evidence_parent
        self.cwd = work / "Foreign current directory"
        self.cwd.mkdir()
        self.started = time.monotonic()
        self.environment = dict(os.environ)
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "FACMAN_RESOURCE_PACK"):
            self.environment.pop(key, None)

    def artifact(self, path: Path) -> dict:
        identity, _ = cases.file_bytes(path, max(LOG_LIMIT, 32 * 1024 * 1024))
        record = {"path": path.relative_to(self.evidence_parent).as_posix(),
                  "bytes": identity["size"], "sha256": identity["sha256"]}
        self.receipt["artifacts"].append(record)
        return record

    def document(self, name: str, value: object) -> dict:
        path = self.work / name
        data = cases.encoded(value)
        cases.require(len(data) <= 32 * 1024 * 1024, "proof document byte budget")
        with path.open("xb") as stream:
            stream.write(data)
        return self.artifact(path)

    def raw(self, label: str, executable: Path, arguments: list[str], *, success: bool = True) -> bytes:
        cases.require(len(self.receipt["commands"]) < 32 and
                      time.monotonic() - self.started < PROOF_TIMEOUT, "proof command/time budget")
        command = [str(executable), *arguments]
        paths = [self.work / (label + suffix) for suffix in (".stdout", ".stderr")]
        record = {"id": label, "command": command, "exit_code": None, "timed_out": False,
                  "output_limit_exceeded": False, "stdout": "", "stderr": "", "error": None}
        self.receipt["commands"].append(record)
        stopped = threading.Event()
        errors = []
        process = None
        workers = []
        files = [path.open("xb") for path in paths]
        try:
            process = subprocess.Popen(command, cwd=self.cwd, env=self.environment,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for pipe, output in zip((process.stdout, process.stderr), files):
                worker = threading.Thread(target=self._pump, args=(pipe, output, stopped, errors), daemon=True)
                worker.start()
                workers.append(worker)
            deadline = time.monotonic() + min(COMMAND_TIMEOUT, PROOF_TIMEOUT - (time.monotonic() - self.started))
            while process.poll() is None:
                if stopped.is_set() or time.monotonic() >= deadline:
                    record["timed_out"] = not stopped.is_set()
                    process.kill()
                    break
                time.sleep(0.02)
            record["exit_code"] = process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError) as error:
            record["error"] = str(error)[:4096]
        finally:
            for worker in workers:
                worker.join(timeout=2)
            if any(worker.is_alive() for worker in workers):
                errors.append("output pipe did not close after child exit")
            for output in files:
                output.close()
            record["output_limit_exceeded"] = stopped.is_set()
            if errors:
                record["error"] = "; ".join(errors)[:4096]
            record["stdout"], record["stderr"] = (self.artifact(path)["path"] for path in paths)
        cases.require(not record["timed_out"] and not record["output_limit_exceeded"] and
                      record["error"] is None and (record["exit_code"] == 0) == success,
                      f"{label}: command failed; retained stdout/stderr and exit record")
        return paths[0].read_bytes()

    @staticmethod
    def _pump(pipe, output, stopped, errors) -> None:
        count = 0
        try:
            with pipe:
                while block := pipe.read(65536):
                    available = max(0, LOG_LIMIT - count)
                    output.write(block[:available])
                    count += len(block)
                    if count > LOG_LIMIT:
                        stopped.set()
                        break
        except (OSError, ValueError) as error:
            errors.append(str(error))
            stopped.set()

    def json(self, label: str, executable: Path, arguments: list[str]) -> dict:
        value = json.loads(self.raw(label, executable, arguments))
        cases.require(value.get("schema") == "facman.transport_response.v2" and
                      isinstance(value.get("payload"), dict) and not value.get("error"),
                      "unexpected resource success envelope")
        return value["payload"]

    def refusal(self, label: str, executable: Path, arguments: list[str], *, prefixes=("resource_",)) -> None:
        value = json.loads(self.raw(label, executable, arguments, success=False))
        error = value.get("error") or {}
        cases.require(self.receipt["commands"][-1]["exit_code"] == 1 and
                      value.get("schema") == "facman.transport_response.v2" and
                      isinstance(error.get("code"), str) and error["code"].startswith(prefixes),
                      "refusal must be typed resource failure, not a crash")


def input_identity(root: Path, names: tuple, before: dict, artifact: dict) -> dict:
    indexed = {row["path"]: row for row in before["files"]}
    records = [{"path": indexed[name]["path"], "bytes": indexed[name]["size"],
                "sha256": indexed[name]["sha256"]} for name in names]
    return {"root": str(root), "executable": records[0], "resource": records[1],
            "manifest": records[2], "inventory_sha256": artifact["sha256"],
            "inventory_artifact": artifact["path"]}


def prove(executable: Path, profile: str, package_mode: str, evidence: Path) -> dict:
    cases.require(profile in cases.PROFILES and package_mode in ("portable", "installed_stage"), "invalid proof input")
    names = cases.PROFILES[profile]
    package_root = executable.absolute().parents[len(Path(names[0]).parts) - 1]
    work, owner = prepare(evidence, package_root)
    report = {"schema": "facman.resource_package_proof.v1", "status": "fail", "profile_id": profile,
              "package_mode": package_mode, "platform": sys.platform, "source_revision": None,
              "source_tree": None, "source_dirty": None,
              "input_provenance": "supplied_path_not_producer_attested", "input": None,
              "executable_sha256": None, "original_unchanged": False, "proof_source_artifact": None,
              "cases": [], "commands": [], "artifacts": [], "failure": None,
              "ownership": owner, "authority": {key: False for key in (
                  "release", "tagging", "signing", "publication", "human_acceptance", "game", "live_installation")}}
    driver = Driver(work, report, evidence.absolute().parent)
    before = source_before = None
    try:
        report.update(source_identity())
        source_before = proof_inputs()
        report["proof_source_artifact"] = driver.document("proof-source.json", source_before)["path"]
        root, names = cases.layout(executable, profile)
        before = cases.snapshot(root)
        inventory = driver.document("input-inventory.json", before["files"])
        driver.document("input-directories.json", before["directories"])
        report["input"] = input_identity(root, names, before, inventory)
        report["executable_sha256"] = report["input"]["executable"]["sha256"]
        oracle = cases.zip_oracle(root / names[1])
        driver.document("resource-oracle.json", oracle)
        complete = lambda name: report["cases"].append({"id": name, "status": "pass"})
        cases.run_cases(driver, root, names, profile, before, oracle, work, complete)
        driver.document("export-inventory.json", cases.snapshot(work / "Exported resources"))
    except Exception as error:
        report["failure"] = str(error)[:4096]
    finish_observations(driver, package_root, before, source_before, report)
    if report["failure"] is None and report["original_unchanged"]:
        report["cases"].append({"id": "original_unchanged", "status": "pass"})
        if [row["id"] for row in report["cases"]] == list(cases.CASE_IDS):
            report["status"] = "pass"
        else:
            report["failure"] = "proof cases incomplete"
    problems = json_contract.validate(report, json_contract.load_schema(SCHEMA))
    if problems:
        report["status"] = "fail"
        report["failure"] = ("resource proof receipt violates schema: " + "; ".join(problems))[:4096]
    data = json.dumps(report, indent=2, sort_keys=True).encode() + b"\n"
    with (work / "validation.json").open("xb") as output:
        output.write(data)
    cases.plain_path(evidence)
    with evidence.absolute().open("xb") as output:
        output.write(data)
    return report


def proof_inputs() -> dict:
    return {name: cases.file_bytes(ROOT / name, MAX_SOURCE)[0] for name in SOURCE_FILES}


def finish_observations(driver, root: Path, before, source_before, report: dict) -> None:
    if before is not None:
        try:
            after = cases.snapshot(root)
            driver.document("input-after.json", after)
            report["original_unchanged"] = before == after
            if not report["original_unchanged"]:
                report["failure"] = "original input package changed during qualification"
        except Exception as error:
            report["failure"] = ("cannot verify original unchanged: " + str(error))[:4096]
    if source_before is not None:
        try:
            identity = source_identity()
            expected = {key: report[key] for key in identity}
            cases.require(proof_inputs() == source_before and identity == expected,
                          "proof source identity changed during qualification")
        except Exception as error:
            report["failure"] = str(error)[:4096]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(cases.PROFILES), required=True)
    parser.add_argument("--package-mode", choices=("portable", "installed_stage"), required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = prove(args.executable, args.profile, args.package_mode, args.evidence)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"resource-package-proof: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "evidence": str(args.evidence),
                      "failure": report["failure"]}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
