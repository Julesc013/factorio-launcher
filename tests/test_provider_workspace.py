# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import development_layout, provider_workspace


class ProviderWorkspaceTests(unittest.TestCase):
    def test_selected_consumer_owns_exact_historical_provider_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            consumer = root / "predecessor"
            (consumer / "release/index").mkdir(parents=True)
            repositories = {}
            identities = {}
            records = []
            for provider_id in provider_workspace.PROVIDERS:
                name = provider_id.replace("_", "-")
                repository = root / name
                repository.mkdir()

                def git(*arguments: str) -> str:
                    return subprocess.run(
                        ["git", "-c", "user.name=FacMan Fixture",
                         "-c", "user.email=fixture@example.invalid", *arguments],
                        cwd=repository, check=True, capture_output=True, text=True,
                    ).stdout.strip()

                git("init")
                (repository / "CMakeLists.txt").write_text("# historical provider\n")
                git("add", "CMakeLists.txt")
                git("commit", "-m", "Historical provider")
                pin, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
                (repository / "CMakeLists.txt").write_text("# newer provider\n")
                git("commit", "-am", "Newer provider")
                self.assertNotEqual(pin, git("rev-parse", "HEAD"))
                repositories[provider_id] = repository
                identities[provider_id] = (pin, tree)
                records.append(
                    f'[[component]]\nid = "{provider_id}"\nsource = "{name}"\n'
                    f'pin = "{pin}"\ntree = "{tree}"\n'
                    f'remote = "https://example.invalid/{name}.git"\n'
                )
            lock = consumer / "release/index/workspace_lock.v1.toml"
            lock.write_text("\n".join(records), encoding="utf-8")
            output = root / "predecessor-output"
            with mock.patch.object(
                provider_workspace, "source_checkout",
                side_effect=lambda component: repositories[component["id"]],
            ):
                roots = provider_workspace.prepare(output, source_root=consumer)
                self.assertEqual(roots, provider_workspace.prepare(output, source_root=consumer))
            marker = development_layout.read_marker(output, consumer)
            self.assertEqual(str(consumer.resolve()), marker["source_root"])
            manifest = json.loads((output / "providers/manifest.v1.json").read_text())
            self.assertEqual(str(lock), manifest["workspace_lock"])
            for provider_id, path in roots.items():
                self.assertTrue(path.is_relative_to(output))
                pin, tree = identities[provider_id]
                self.assertEqual(pin, provider_workspace.capture(
                    provider_workspace.git_command("rev-parse", "HEAD"), path
                ))
                self.assertEqual(tree, provider_workspace.capture(
                    provider_workspace.git_command("rev-parse", "HEAD^{tree}"), path
                ))
                self.assertEqual("# historical provider\n", (path / "CMakeLists.txt").read_text())

    def test_git_commands_enable_and_persist_windows_long_paths(self) -> None:
        self.assertEqual(
            provider_workspace.git_command("status", "--porcelain=v1"),
            ["git", "-c", "core.longpaths=true", "status", "--porcelain=v1"],
        )
        clone = provider_workspace.git_command(
            "clone",
            "--no-checkout",
            "--no-hardlinks",
            "-c",
            "core.longpaths=true",
            "source",
            "destination",
        )
        self.assertEqual(clone.count("core.longpaths=true"), 2)
        self.assertLess(clone.index("core.longpaths=true"), clone.index("clone"))
        self.assertGreater(clone.index("core.longpaths=true", 4), clone.index("clone"))

    def test_lock_has_exact_provider_identities(self) -> None:
        components = provider_workspace.locked_components()
        self.assertEqual(set(provider_workspace.PROVIDERS), set(components))
        for component in components.values():
            self.assertEqual(40, len(component["pin"]))
            self.assertEqual(40, len(component["tree"]))
            self.assertTrue(component["remote"].startswith("https://github.com/"))

    def test_cmake_arguments_are_exact_and_credential_free(self) -> None:
        roots = {
            "universal_launcher": Path("C:/provider-cache/universal-launcher"),
            "universal_setup": Path("C:/provider-cache/universal-setup"),
        }
        arguments = provider_workspace.cmake_arguments(roots)
        self.assertEqual(3, len(arguments))
        self.assertIn("FLAUNCH_UNIVERSAL_LAUNCHER_ROOT", arguments[0])
        self.assertIn("FLAUNCH_UNIVERSAL_SETUP_ROOT", arguments[1])
        self.assertIn("FACMAN_PROVIDER_LOCK_FILE", arguments[2])
        self.assertNotIn("@", "".join(arguments))


if __name__ == "__main__":
    unittest.main()
