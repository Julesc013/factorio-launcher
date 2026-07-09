from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import repro_workspace_smoke


class ReproWorkspaceSmokeTests(unittest.TestCase):
    def test_workspace_root_resolves_grouped_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            factorio = make_repo(workspace / "Factorio" / "factorio-launcher", "factorio-launcher")
            setup = make_repo(workspace / "Universal" / "universal-setup", "universal-setup")
            launcher = make_repo(workspace / "Universal" / "universal-launcher", "universal-launcher")

            repos = repro_workspace_smoke.resolve_workspace_repos(workspace_root=workspace)

        self.assertEqual(repos["factorio-launcher"], factorio.resolve(strict=False))
        self.assertEqual(repos["universal-setup"], setup.resolve(strict=False))
        self.assertEqual(repos["universal-launcher"], launcher.resolve(strict=False))

    def test_check_workspace_accepts_minimal_checkout_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repos = {
                "factorio-launcher": make_repo(workspace / "factorio-launcher", "factorio-launcher"),
                "universal-setup": make_repo(workspace / "universal-setup", "universal-setup"),
                "universal-launcher": make_repo(workspace / "universal-launcher", "universal-launcher"),
            }

            problems = repro_workspace_smoke.check_workspace(repos, require_git=True)

        self.assertEqual(problems, [])

    def test_check_workspace_rejects_factorio_owned_ulk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repos = {
                "factorio-launcher": make_repo(workspace / "factorio-launcher", "factorio-launcher"),
                "universal-setup": make_repo(workspace / "universal-setup", "universal-setup"),
                "universal-launcher": make_repo(workspace / "universal-launcher", "universal-launcher"),
            }
            repos["factorio-launcher"].joinpath("include", "ulk").mkdir(parents=True)

            problems = repro_workspace_smoke.check_workspace(repos, require_git=True)

        self.assertTrue(any("must not own sibling implementation path include/ulk" in problem for problem in problems))

    def test_check_workspace_rejects_factorio_path_in_universal_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repos = {
                "factorio-launcher": make_repo(workspace / "factorio-launcher", "factorio-launcher"),
                "universal-setup": make_repo(workspace / "universal-setup", "universal-setup"),
                "universal-launcher": make_repo(workspace / "universal-launcher", "universal-launcher"),
            }
            repos["universal-launcher"].joinpath("runtime", "factorio").mkdir(parents=True)

            problems = repro_workspace_smoke.check_workspace(repos, require_git=True)

        self.assertTrue(any("contains product-specific path runtime/factorio" in problem for problem in problems))


def make_repo(root: Path, name: str) -> Path:
    root.mkdir(parents=True)
    root.joinpath(".git").mkdir()
    for marker in repro_workspace_smoke.REPO_MARKERS[name]:
        path = root / marker
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{marker}\n", encoding="utf-8")
    if name == "factorio-launcher":
        (root / "include" / "flb").mkdir(parents=True, exist_ok=True)
    return root


if __name__ == "__main__":
    unittest.main()
