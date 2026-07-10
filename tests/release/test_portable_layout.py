from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tools import package_layout_check

ROOT = Path(__file__).resolve().parents[2]


class PortableLayoutTests(unittest.TestCase):
    def test_windows_portable_cli_is_static_first_and_target_specific(self) -> None:
        profile = load_toml(ROOT / "release/profiles/windows_portable_cli_x64/profile.toml")
        bundle = expanded_bundle(profile)
        destinations = component_destinations(bundle)
        self.assertEqual(profile["target_os"], "windows")
        self.assertEqual(profile["target_arch"], "x64")
        self.assertEqual(profile["linkage"]["model"], "static_first")
        self.assertEqual(profile["required_components"]["libraries"], [])
        self.assertEqual(destinations, {"bin/facman.exe", "contracts/schema", "content/factorio"})

    def test_portable_cli_is_self_contained(self) -> None:
        profile = load_toml(ROOT / "release/profiles/portable_cli_x64/profile.toml")
        bundle = expanded_bundle(profile)
        destinations = component_destinations(bundle)
        for expected in [
            "bin/facman",
            "lib/ulk",
            "lib/usk",
            "lib/flb_factorio",
            "contracts/schema",
            "content/factorio",
        ]:
            self.assertIn(expected, destinations)

    def test_portable_tui_keeps_cli_and_tui_separate(self) -> None:
        profile = load_toml(ROOT / "release/profiles/portable_tui_x64/profile.toml")
        entrypoints = profile["entrypoints"]
        self.assertEqual(entrypoints["cli"], "bin/facman")
        self.assertEqual(entrypoints["tui"], "bin/facman-tui")
        self.assertNotEqual(entrypoints["cli"], entrypoints["tui"])


def expanded_bundle(profile: dict[str, object]) -> dict[str, object]:
    path = ROOT / str(profile["package_manifest"])
    return package_layout_check.expand_bundle_manifest(path, load_toml(path), [])


def component_destinations(bundle: dict[str, object]) -> set[str]:
    components = bundle.get("components", [])
    self_contained: set[str] = set()
    if isinstance(components, list):
        for component in components:
            if isinstance(component, dict):
                destination = str(component.get("destination", ""))
                self_contained.add(package_layout_check.normalize_layout_path(destination))
    return self_contained


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
