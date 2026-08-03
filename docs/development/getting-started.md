# Development getting started

Requirements are CMake 3.20+, a C/C++ toolchain, and Python 3.11+ for repository
tooling. The product runtime does not depend on Python. Universal Launcher and
Universal Setup must be available at the paths resolved by the root CMake
configuration and pinned by `release/index/workspace_lock.v1.toml`.

```powershell
$taskId = 'FACMAN-LOCAL-VERIFY-01'
$buildRoot = "E:\Temporary\FacMan\$taskId\native-smoke"
py -3 tools/workspace_config.py doctor
cmake -S . -B $buildRoot -DFACMAN_BUILD_TESTS=ON
cmake --build $buildRoot --config Debug --parallel
ctest --test-dir $buildRoot -C Debug --output-on-failure
py -3 tools/dev.py test --fast --build-root $buildRoot
```

`doctor` requires both Universal repository `HEAD`s to match
`release/index/workspace_lock.v1.toml`. It reports drift without checking out,
switching, or otherwise aligning either dependency.

The CLI is normally `$buildRoot\Debug\facman.exe` on a multi-config Windows
build and `$buildRoot/facman` on a single-config Unix build.
Use `tools/dev.py test --affected` while iterating and `verify-all` before a
promotion handoff. Pass the same task-owned root with
`tools/dev.py verify-all --build-root $buildRoot`. `verify-all` checks the
pinned dependency revisions before building or running tests and applies the
promotion test-obligation profile.

New build and package output for all three canonical repositories belongs under
`E:\Temporary\FacMan\<task-id>`, never under an in-repository `build/` tree.
See [Build Root Hygiene](build-root-hygiene.md).

Current project truth is generated into `.aide/memory/project-state.v2.json`.
Run `py -3 tools/project_state.py --write` after changing its canonical inputs.
The compact tracked view is `release/index/current_state.v1.toml`. Its revision
fields are reviewed-checkpoint compatibility fields, not a claim about the live
checkout containing the file.

Generate live checkout/provider truth outside the source tree after aligning
the sibling repositories:

```powershell
$observationRoot = "E:\Temporary\FacMan\FACMAN-CURRENT-TRUTH-01\observation"
py -3 tools/current_checkout_observation.py `
  --provider-root universal_launcher=..\universal-launcher `
  --provider-root universal_setup=..\universal-setup `
  --expected-source-sha (git rev-parse HEAD) `
  --line-ending-profile windows_checkout `
  --output-dir $observationRoot
```

The command emits canonical JSON and a Markdown rendering from the same data.
The output root must be outside FacMan and every passed provider checkout, so
artifact generation cannot dirty a repository after observing it as clean.
Every evidence-producing Git read uses the selected profile from
`release/index/checkout_observation_policy.v1.toml`; the effective
`core.autocrlf` and `core.eol` values and the policy digest are recorded. The
command disables lazy fetching and fails before HEAD, pin, reachability, or ABI
claims when it finds repository-local config includes, object alternates, a
shallow checkout, partial-clone/promisor config, or promisor pack markers.

The command performs no fetch. `origin/main` evidence is explicitly
`local_tracking_ref_only`, with `fetch_performed=false` and `fetched_at=null`.
It therefore does not prove current remote state or source closure. Use
`tools/remote_source_closure.py` for the separate fetched, empty-clone
source-closure proof. It also fails closed on a dirty or unexpected FacMan
checkout, provider pin drift, origin mismatch, a missing local tracking ref,
an unreachable pin, or an unavailable ABI declaration.

Archived AIDE history is discoverable through `.aide/history/<checkpoint>/index.json`
but excluded from normal context packets.
