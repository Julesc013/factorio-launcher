# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

import unittest
from pathlib import Path

from tools import provider_workspace


class ProviderWorkspaceTests(unittest.TestCase):
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
