# Repro Workspace Smoke

`tools/repro_workspace_smoke.py` is the repeatable proof that a checkout can find
and validate the three repositories without machine-specific source edits.

Use the quick check after cloning or moving folders:

```powershell
py -3 tools/repro_workspace_smoke.py
```

The quick check verifies:

- `factorio-launcher`, `universal-setup`, and `universal-launcher` are Git
  checkouts.
- required ABI, runtime, contract, and build marker files exist.
- FacMan does not vendor `usk` or `ulk` implementation paths.
- Universal Launcher does not grow setup or Factorio product paths.
- Universal Setup does not grow launcher or Factorio product paths.

Use `--workspace-root` when validating a fresh clone from outside the target
Factorio checkout:

```powershell
py -3 D:/Projects/Factorio/factorio-launcher/tools/repro_workspace_smoke.py `
  --workspace-root D:/Projects/facman-repro-YYYYMMDD-HHMMSS
```

Both flat and grouped layouts are supported:

```text
workspace/
  factorio-launcher/
  universal-launcher/
  universal-setup/

workspace/
  Factorio/factorio-launcher/
  Universal/universal-launcher/
  Universal/universal-setup/
```

Use the full build mode for publication or branch handoff proof:

```powershell
py -3 tools/repro_workspace_smoke.py --build
```

The build matrix binds package tests to its own out-of-tree native build and
explicitly enables the target-specific TUI. It never borrows artifacts from a
checkout-local build directory, so missing frontend components fail the proof
instead of being hidden by stale developer outputs.

Full build mode uses out-of-tree build directories under a temp
`facman-repro-smoke` root keyed by the resolved checkout paths. That avoids stale
`CMakeCache.txt` failures when repositories are moved between parent folders.
Use `--build-root <path>` to choose an explicit scratch build root.

Full build mode runs:

```text
universal-launcher:
  cmake -S . -B build/native-smoke
  cmake --build build/native-smoke
  ctest --test-dir build/native-smoke -C Debug --output-on-failure

universal-setup:
  cmake -S . -B build/native-smoke
  cmake --build build/native-smoke
  ctest --test-dir build/native-smoke -C Debug --output-on-failure

factorio-launcher:
  py -3 .aide/scripts/aide_lite.py test
  py -3 tools/strict_check.py
  py -3 -m unittest discover -s tests -v
  cmake -S . -B build/native-smoke
  cmake --build build/native-smoke
  ctest --test-dir build/native-smoke -C Debug --output-on-failure
```

Use `--no-require-git` for unpacked source archives, and `--require-clean` when
the handoff must prove there are no local working-tree changes.
