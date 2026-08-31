# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import io
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

from tools import alpha3_release_assets, self_contained_setup


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0-alpha.3"
EXPECTED = [
    f"FacMan-{VERSION}-windows-x64-portable.zip",
    f"FacMan-{VERSION}-windows-x64-setup.exe",
    f"FacMan-{VERSION}-macos-x64-portable.zip",
    f"FacMan-{VERSION}-macos-x64-setup.pkg",
    f"FacMan-{VERSION}-linux-x64-portable.tar.zst",
    f"FacMan-{VERSION}-linux-x64-setup.run",
    f"FacMan-{VERSION}-SHA256SUMS.txt",
    f"FacMan-{VERSION}-evidence.zip",
]


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


class Alpha3DistributionTests(unittest.TestCase):
    def test_exact_authored_asset_set(self) -> None:
        source = load_toml(ROOT / "release/index/alpha3_release_source.v1.toml")
        self.assertEqual(source["version"], VERSION)
        self.assertEqual(source["tag"], f"v{VERSION}")
        self.assertEqual(source["asset_count"], 8)
        self.assertEqual(source["inventory"]["assets"], EXPECTED)
        self.assertEqual(len(set(EXPECTED)), 8)
        forbidden = ("cli-", "tui-", "winforms", "appkit", "gtk", ".json")
        for name in EXPECTED:
            self.assertFalse(any(value in name.lower() for value in forbidden), name)

    def test_release_limitations_follow_the_alpha3_source_schema(self) -> None:
        source = load_toml(ROOT / "release/index/alpha3_release_source.v1.toml")
        self.assertNotIn("known_limitations", source)
        limitations = alpha3_release_assets.release_known_limitations(source)
        self.assertGreaterEqual(len(limitations), 5)
        self.assertTrue(all(limitations))

    def test_product_profiles_expose_one_gui_and_one_terminal_host(self) -> None:
        expectations = {
            "windows_product_x64": ("FacMan.exe", "bin/facman.exe"),
            "macos_product_x64": (
                "FacMan.app/Contents/MacOS/FacMan",
                "FacMan.app/Contents/MacOS/facman",
            ),
            "linux_product_x64": ("FacMan", "facman"),
        }
        for profile_id, (gui, terminal) in expectations.items():
            profile = load_toml(
                ROOT / "release/profiles" / profile_id / "profile.toml"
            )
            entrypoints = profile["entrypoints"]
            self.assertEqual(entrypoints["gui"], gui)
            self.assertEqual(entrypoints["cli"], terminal)
            self.assertEqual(entrypoints["tui"], terminal)
            self.assertNotIn("facman-tui", str(profile).lower())

    def test_windows_setup_embeds_the_unified_portable_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-alpha3-setup-test-") as raw:
            root = Path(raw)
            portable = root / EXPECTED[0]
            with zipfile.ZipFile(portable, "w") as archive:
                archive.writestr("FacMan.exe", b"gui")
                archive.writestr("bin/facman.exe", b"terminal")
                archive.writestr("manifest/package.v1.toml", b"schema='test'\n")
            bootstrap = root / "FacManSetup.exe"
            bootstrap.write_bytes(b"MZ synthetic bootstrap")
            output = root / "output"
            record = self_contained_setup.build(
                portable,
                bootstrap,
                output,
                version=VERSION,
                facman_revision="1" * 40,
                usk_revision="2" * 40,
                dirty=False,
            )
            setup = output / EXPECTED[1]
            self.assertTrue(setup.is_file())
            self.assertEqual(record["setup"]["filename"], EXPECTED[1])
            with zipfile.ZipFile(setup) as archive:
                names = set(archive.namelist())
            overlay = setup.read_bytes()[record["embedded_payload"]["archive_offset"] :]
            with zipfile.ZipFile(io.BytesIO(overlay)) as archive:
                self.assertEqual(set(archive.namelist()), names)
            self.assertIn(
                f"facman/generations/{VERSION}/FacMan.exe", names
            )
            self.assertIn(
                f"facman/generations/{VERSION}/bin/facman.exe", names
            )
            self.assertIn("facman/maintenance/FacManSetup.exe", names)

    def test_windows_layout_has_no_case_fold_collision(self) -> None:
        bundle = load_toml(
            ROOT / "release/packaging/windows/platform_product.v1.toml"
        )
        destinations = [
            str(component["destination"]) for component in bundle["components"]
        ]
        folded = [value.casefold() for value in destinations]
        self.assertEqual(len(folded), len(set(folded)))
        self.assertIn("FacMan.exe", destinations)
        self.assertIn("bin/facman.exe", destinations)

    def test_alpha2_supersession_is_forward_only(self) -> None:
        record = load_toml(
            ROOT / "release/ledger/0.1.0-alpha.2/supersession.v1.toml"
        )
        self.assertEqual(record["successor"], VERSION)
        self.assertTrue(record["immutable"])
        self.assertFalse(record["assets_replaced"])

    def test_hosted_product_builds_bind_explicit_source_observations(self) -> None:
        workflow = (
            ROOT / ".github/workflows/alpha3-product-release.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            workflow.count("- name: Record release-eligible source observation"),
            3,
        )
        package_commands = [
            line
            for line in workflow.splitlines()
            if "python tools/package_build.py" in line
            and any(
                profile in line
                for profile in (
                    "windows_product_x64",
                    "macos_portable_cli_x64",
                    "linux_portable_cli_x64",
                )
            )
        ]
        self.assertEqual(len(package_commands), 3)
        self.assertEqual(workflow.count("release-source-observation.v1.json"), 6)
        self.assertEqual(
            workflow.count("python tools/ci_checkout_credential_scrub.py"),
            1,
        )
        self.assertEqual(workflow.count("Prepare no-link temporary root"), 1)

    def test_release_job_checks_clean_tag_before_downloading_inputs(self) -> None:
        workflow = (
            ROOT / ".github/workflows/alpha3-product-release.yml"
        ).read_text(encoding="utf-8")
        release_job = workflow[workflow.index("  draft-release:") :]
        tag_check = release_job.index("- name: Verify immutable annotated tag")
        download = release_job.index("- name: Download exact qualified inputs")
        self.assertLess(tag_check, download)
        self.assertIn('test -z "$(git status --porcelain=v1)"', release_job)


if __name__ == "__main__":
    unittest.main()
