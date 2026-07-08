from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import workspace_config


class WorkspaceConfigTests(unittest.TestCase):
    def test_workspace_root_resolves_universal_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            setup = workspace / "Universal" / "universal-setup"
            launcher = workspace / "Universal" / "universal-launcher"
            setup.mkdir(parents=True)
            launcher.mkdir(parents=True)
            setup.joinpath("CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8")
            launcher.joinpath("CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8")

            with patch.dict("os.environ", {"FLAUNCH_WORKSPACE_ROOT": str(workspace)}, clear=True):
                repos = workspace_config.resolved_repos()

        self.assertEqual(repos["universal-setup"], setup.resolve(strict=False))
        self.assertEqual(repos["universal-launcher"], launcher.resolve(strict=False))
        command = workspace_config.cmake_command(repos)
        self.assertIn("-DFLAUNCH_UNIVERSAL_SETUP_ROOT=", command)
        self.assertIn(setup.as_posix(), command)
        presets = workspace_config.cmake_user_presets(repos)
        cache = presets["configurePresets"][0]["cacheVariables"]  # type: ignore[index]
        self.assertEqual(cache["FLAUNCH_UNIVERSAL_LAUNCHER_ROOT"], launcher.as_posix())


if __name__ == "__main__":
    unittest.main()
