from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import package_skeleton_build, package_skeleton_check


class PackageSkeletonTests(unittest.TestCase):
    def test_build_and_validate_all_skeletons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "package-skeletons"
            built = package_skeleton_build.materialize_all(root)
            self.assertEqual(len(built), 8)
            self.assertEqual(package_skeleton_check.validate_root(root), [])

    def test_builder_refuses_unowned_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "unowned"
            root.mkdir()
            valuable = root / "operator-data.txt"
            valuable.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unowned output root"):
                package_skeleton_build.materialize_all(root)
            self.assertEqual(valuable.read_text(encoding="utf-8"), "preserve\n")

    def test_missing_contracts_fails(self) -> None:
        with built_skeletons() as root:
            shutil.rmtree(root / "windows_legacy_winforms_x64" / "contracts")
            self.assertProblem(root, "missing contracts directory")

    def test_missing_content_fails(self) -> None:
        with built_skeletons() as root:
            shutil.rmtree(root / "portable_cli_x64" / "content")
            self.assertProblem(root, "missing content directory")

    def test_missing_entrypoint_fails(self) -> None:
        with built_skeletons() as root:
            (root / "portable_tui_x64" / "bin" / "facman-tui.placeholder").unlink()
            self.assertProblem(root, "missing tui entrypoint placeholder")

    def test_duplicate_destination_fails(self) -> None:
        with built_skeletons() as root:
            components = root / "portable_cli_x64" / "manifest" / "components.v1.toml"
            append_component(components, name="duplicate_cli", destination="bin/facman")
            self.assertProblem(root, "duplicate package destination bin/facman")

    def test_absolute_destination_fails(self) -> None:
        with built_skeletons() as root:
            components = root / "portable_cli_x64" / "manifest" / "components.v1.toml"
            append_component(components, name="absolute_bad", destination="/tmp/facman")
            self.assertProblem(root, "must be relative")

    def test_forbidden_factorio_payload_fails(self) -> None:
        with built_skeletons() as root:
            bad = root / "portable_cli_x64" / "bin" / "factorio.exe.placeholder"
            bad.write_text("forbidden game payload\n", encoding="utf-8")
            self.assertProblem(root, "forbidden package skeleton payload marker factorio.exe")

    def test_forbidden_secret_marker_fails(self) -> None:
        with built_skeletons() as root:
            bad = root / "portable_cli_x64" / "manifest" / "token.txt"
            bad.write_text("forbidden secret filename\n", encoding="utf-8")
            self.assertProblem(root, "forbidden package skeleton payload marker token")

    def test_incorrect_linux_entrypoint_path_fails(self) -> None:
        with built_skeletons() as root:
            marker = root / "linux_x11_gtk_x64" / "usr" / "share" / "facman" / "manifest" / "skeleton.v1.json"
            data = json.loads(marker.read_text(encoding="utf-8"))
            data["entrypoints"]["gui"] = "usr/bin/facman-gui"
            marker.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertProblem(root, "Linux GTK gui entrypoint must be usr/bin/facman-gui-gtk")

    def test_macos_executable_under_resources_fails(self) -> None:
        with built_skeletons() as root:
            bad = (
                root
                / "macos_legacy_appkit_x64"
                / "FacMan.app"
                / "Contents"
                / "Resources"
                / "BadExecutable.placeholder"
            )
            bad.write_text("bad executable placement\n", encoding="utf-8")
            self.assertProblem(root, "executable/library placeholder under Resources")

    def test_windows_gui_package_missing_cli_fails(self) -> None:
        with built_skeletons() as root:
            (root / "windows_legacy_winforms_x64" / "bin" / "facman.exe.placeholder").unlink()
            self.assertProblem(root, "missing cli entrypoint placeholder")

    def assertProblem(self, root: Path, expected: str) -> None:
        problems = package_skeleton_check.validate_root(root)
        self.assertTrue(
            any(expected in problem for problem in problems),
            f"expected {expected!r} in {problems!r}",
        )


class built_skeletons:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "package-skeletons"
        package_skeleton_build.materialize_all(self.root)
        return self.root

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._tmp.cleanup()


def append_component(path: Path, name: str, destination: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    "[[component]]",
                    f'name = "{name}"',
                    'source_target = "fixture"',
                    f'destination = "{destination}"',
                    f'placeholder = "{destination}.placeholder"',
                    "",
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
