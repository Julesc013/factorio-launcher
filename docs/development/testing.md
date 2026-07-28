# Testing

CTest and Python suites use the categories `fast-unit`, `contract`,
`integration`, `filesystem`, `archive`, `transaction`, `package`, `platform`,
`fuzz`, and `operator`. The operator category deliberately cannot auto-pass.

```powershell
py -3 tools/dev.py test --affected
py -3 tools/dev.py test --fast
py -3 tools/dev.py test --category contract
py -3 tools/dev.py test --full
py -3 tools/dev.py verify-all
```

`test --fast` is the canonical inner loop: it builds only the native targets
present in the configured CTest graph and labelled `fast-unit`, then runs the
focused Python policy/metadata suite. Required and optional fast tests are
declared separately. A TUI-off graph therefore does not request a nonexistent
TUI target, while a TUI-on graph automatically includes it. Policy drift in
either direction fails closed.

`verify-all` is the canonical exhaustive local gate: it builds the default
native graph, runs all CTest and Python tests, then runs every strict validator.
It is intentionally slower and is required before a WorkUnit closeout; a green
fast run does not replace it. The first gate is a read-only comparison of both
Universal dependency `HEAD`s with the workspace lock; a mismatch stops the run
without aligning branches.

Every Python skip begins with one obligation class:

```text
required_blocked
unsupported
optional
not_applicable
historical_only
```

The promotion profile permits zero `required_blocked` skips and zero unknown
skip reasons. Hosted Windows, Linux, and macOS lanes use that profile. Test and
package counts remain validation totals rather than product-readiness metrics.

Developer commands derive a stable external per-user task root by default.
On Windows it is beneath `%LOCALAPPDATA%\FacMan\Tasks`; other platforms use
the configured cache root or operating-system temporary root. Set
`FACMAN_TASK_ROOT` or pass `--task-root` for a named retained root.
Full runs persist their classified skip summary beneath
`<task-root>/evidence/python-obligations-<profile>.json`.

The affected map is `contracts/policy/test_impact.v1.json`. It selects focused
native targets, Python modules, strict validators, and platform package lanes.
Inventory floors detect test removal, but passing affected validation does not
replace Debug/Release, sanitizer, fuzz, coverage, ABI, package, or target-CI
promotion evidence.

Performance baselines are advisory on shared machines. Use
`tools/benchmark.py --compare`; reserve `--enforce` for a stable dedicated
runner. See `docs/architecture/test-architecture-and-native-quality.v1.md`.
