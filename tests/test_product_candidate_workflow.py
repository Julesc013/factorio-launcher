# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import textwrap
import unittest
from pathlib import Path

from tools import ci_proof_check


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/product-candidate.yml"
CANDIDATE_TOOL = ROOT / "tools/product_candidate.py"
EVIDENCE_TOOL = ROOT / "tools/package/candidate_evidence.py"


class ProductCandidateWorkflowTests(unittest.TestCase):
    def test_workflow_is_manual_read_only_and_non_publishing(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        triggers = ci_proof_check.top_level_block(workflow, "on")
        self.assertIn("  workflow_dispatch:", triggers)
        self.assertNotIn("  push:", triggers)
        self.assertNotIn("  pull_request:", triggers)
        self.assertIn("permissions:\n  contents: read", workflow)
        for forbidden in (
            "gh release create",
            "gh release upload",
            "git tag",
            "signtool",
            "codesign",
            "notarytool",
        ):
            self.assertNotIn(forbidden, workflow)

    def test_workflow_derives_version_and_provider_pins_from_tracked_truth(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for anchor in (
            "release/index/version.v2.toml",
            "release/index/workspace_lock.v1.toml",
            "release/index/providers.lock.v2.toml",
            "from tools.release_programme_check import SEMVER_PATTERN",
            "python tools/provider_workspace.py",
            "python tools/release_coherence_proof.py",
            'Path(os.environ["RUNNER_TEMP"])',
            "python tools/product_candidate.py platform-record",
            "python tools/product_candidate.py bundle",
        ):
            self.assertIn(anchor, workflow)
        self.assertNotIn("${sourceDir}/build", json.dumps(json.loads(
            (ROOT / "CMakePresets.json").read_text(encoding="utf-8")
        )))

    def test_runner_temp_roots_are_bound_in_steps_and_revalidated(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("      FACMAN_TASK_ROOT: ${{ runner.temp }}", workflow)
        self.assertNotIn("      FACMAN_BUNDLE_ROOT: ${{ runner.temp }}", workflow)
        for anchor in (
            "Bind marker-owned external platform task root",
            "development_layout.ensure_task_root(",
            'Path(os.environ["RUNNER_TEMP"])',
            'output.write(f"FACMAN_TASK_ROOT={task_root}\\n")',
            "Bind validated external candidate bundle root",
            "from tools.product_candidate import external",
            'output.write(f"FACMAN_BUNDLE_ROOT={bundle_root}\\n")',
        ):
            self.assertIn(anchor, workflow)
        task_binding = workflow.index("Bind marker-owned external platform task root")
        task_use = workflow.index("Materialize marker-owned locked provider workspace")
        bundle_binding = workflow.index("Bind validated external candidate bundle root")
        bundle_use = workflow.index("Download this run's exact platform inputs")
        self.assertLess(task_binding, task_use)
        self.assertLess(bundle_binding, bundle_use)

    def test_windows_scrubs_checkout_credentials_before_observation(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = "Remove checkout-owned temporary credential includes"
        self.assertEqual(1, workflow.count(marker))
        scrub = workflow.index(marker)
        platform = workflow.index("  platform:")
        setup_python = workflow.index("actions/setup-python@", platform)
        task_binding = workflow.index("Bind marker-owned external platform task root")
        observation = workflow.index("Record exact checkout and provider observation")
        self.assertLess(setup_python, scrub)
        self.assertLess(scrub, task_binding)
        self.assertLess(task_binding, observation)
        step = workflow[scrub:task_binding]
        for anchor in (
            "if: ${{ matrix.platform == 'windows' }}",
            "shell: pwsh",
            "python tools/ci_checkout_credential_scrub.py",
            "--repo .",
            '--runner-temp "$env:RUNNER_TEMP"',
        ):
            self.assertIn(anchor, step)
        self.assertEqual(1, workflow.count("python tools/ci_checkout_credential_scrub.py"))
        self.assertEqual(1, workflow.count('--runner-temp "$env:RUNNER_TEMP"'))
        self.assertNotIn("continue-on-error", step)
        self.assertNotIn("|| true", step)

    def test_macos_binds_no_link_temporary_root_before_native_work(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        marker = "Prepare no-link macOS temporary root"
        self.assertEqual(1, workflow.count(marker))
        task_binding = workflow.index("Bind marker-owned external platform task root")
        temporary_root = workflow.index(marker)
        configure = workflow.index("Configure macOS Intel static product core")
        self.assertLess(task_binding, temporary_root)
        self.assertLess(temporary_root, configure)
        step = workflow[temporary_root:workflow.index("Configure MSBuild")]
        for anchor in (
            "if: ${{ matrix.platform == 'macos' }}",
            "shell: bash",
            'export TMPDIR="$FACMAN_TASK_ROOT/native-tmp"',
            'mkdir -p "$TMPDIR"',
            'test "$(python -c \'import os; print(os.path.realpath(os.environ["TMPDIR"]))\')" = "$TMPDIR"',
            'echo "TMPDIR=$TMPDIR" >> "$GITHUB_ENV"',
        ):
            self.assertIn(anchor, step)
        self.assertNotIn("continue-on-error", step)
        self.assertNotIn("|| true", step)

    def test_embedded_python_tool_imports_bind_checkout_to_pythonpath(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        tool_import = re.compile(
            r"(?m)^\s*(?:from tools(?:\.|\s)|import tools(?:\.|\s|$))"
        )
        importing_steps = [
            step
            for step in workflow.split("\n      - name: ")
            if "shell: python" in step and tool_import.search(step)
        ]
        self.assertEqual(4, len(importing_steps))
        for step in importing_steps:
            self.assertIn("PYTHONPATH: ${{ github.workspace }}", step)
        self.assertEqual(
            len(importing_steps),
            workflow.count("PYTHONPATH: ${{ github.workspace }}"),
        )

    def test_workflow_assembles_exact_canonical_six_asset_names(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        candidate_contract = "\n".join(
            path.read_text(encoding="utf-8") for path in (CANDIDATE_TOOL, EVIDENCE_TOOL)
        )
        suffixes = (
            "windows-x64-portable.zip",
            "windows-x64-setup.exe",
            "macos-x64-portable.zip",
            "macos-x64-setup.pkg",
            "linux-x64-portable.tar.zst",
            "linux-x64-setup.run",
        )
        for suffix in suffixes:
            self.assertIn(f'"{suffix}"', candidate_contract)
        self.assertIn("FacMan.app/Contents/Helpers/facman", workflow)
        self.assertNotIn("FacMan.app/Contents/MacOS/facman", workflow)
        self.assertIn('BUNDLE_SCHEMA = "facman.product_candidate_bundle.v1"', candidate_contract)
        self.assertIn('CANDIDATE_CLASS = "unsigned_unpublished_manual_workflow"', candidate_contract)
        self.assertIn('"publication": False', candidate_contract)
        self.assertIn('"signing": False', candidate_contract)

    def test_workflow_requires_exact_setup_payload_equivalence(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        for anchor in (
            "--payload-zip",
            "--canonical-artifact",
            "--payload-artifact",
            "windows_setup_overlay_v1",
            "macos_pkg_root_v1",
            "linux_run_embedded_archive_v1",
            "windows-payload-equivalence.v1.json",
            "macos-payload-equivalence.v1.json",
            "linux-payload-equivalence.v1.json",
        ):
            self.assertIn(anchor, workflow)
        self.assertEqual(3, workflow.count("--canonical-artifact"))
        self.assertEqual(3, workflow.count("--payload-artifact"))

    def test_workflow_qualifies_portable_and_installed_workspace_lifecycles(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        setup_lifecycle = (
            ROOT / "tests/integration/facman_self_setup_lifecycle.py"
        ).read_text(encoding="utf-8")
        combined = workflow + setup_lifecycle
        self.assertEqual(6, combined.count("workspace_lifecycle_package_proof.py"))
        self.assertEqual(3, combined.count("--package-mode portable"))
        self.assertEqual(3, combined.count("installed_stage"))
        for platform in ("windows", "macos", "linux"):
            for mode in ("portable", "installed"):
                self.assertIn(
                    f"{platform}-{mode}-workspace-lifecycle.v1.json",
                    workflow,
                )

    def test_workflow_binds_exact_run_attempt_and_verifies_before_upload(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "python -m unittest tests.test_product_candidate "
            "tests.test_product_candidate_workflow",
            workflow,
        )
        for platform in ("windows", "macos", "linux"):
            self.assertIn(
                f"product-candidate-input-{platform}-${{{{ github.run_id }}}}-"
                "${{ github.run_attempt }}-${{ github.sha }}",
                workflow,
            )
        self.assertIn(
            "product-candidate-input-${platform}-${GITHUB_RUN_ID}-"
            "${GITHUB_RUN_ATTEMPT}-${GITHUB_SHA}",
            workflow,
        )
        for argument in ("--repository", "--workflow-ref", "--job"):
            self.assertEqual(2, workflow.count(argument))
        self.assertIn('--platform-job "platform"', workflow)
        verify = workflow.index("python tools/product_candidate.py verify")
        upload = workflow.index("- name: Upload exact six assets and evidence")
        self.assertLess(verify, upload)
        self.assertNotIn("- name:", workflow[verify:upload])
        self.assertIn(
            "unsigned-unpublished-candidate-${{ github.run_id }}-"
            "${{ github.run_attempt }}-${{ github.sha }}",
            workflow,
        )

    def test_workflow_stays_within_its_reviewability_ratchet(self) -> None:
        self.assertLessEqual(len(WORKFLOW.read_text(encoding="utf-8").splitlines()), 516)

    def test_all_external_actions_remain_immutably_pinned(self) -> None:
        problems = ci_proof_check.validate_immutable_action_pins(
            {WORKFLOW.name: WORKFLOW.read_text(encoding="utf-8")}
        )
        self.assertEqual([], problems)

    def test_embedded_python_steps_compile(self) -> None:
        lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
        scripts = []
        for index, line in enumerate(lines):
            if line.strip() != "shell: python":
                continue
            run_index = index + 1
            while run_index < len(lines) and lines[run_index].strip() == "":
                run_index += 1
            self.assertEqual("run: |", lines[run_index].strip())
            run_indent = len(lines[run_index]) - len(lines[run_index].lstrip())
            body = []
            for candidate in lines[run_index + 1 :]:
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= run_indent:
                    break
                body.append(candidate)
            scripts.append(textwrap.dedent("\n".join(body)))
        self.assertGreaterEqual(len(scripts), 4)
        for index, script in enumerate(scripts):
            compile(script, f"product-candidate-python-step-{index}", "exec")


if __name__ == "__main__":
    unittest.main()
