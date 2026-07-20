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
labelled `fast-unit` and runs the focused Python policy/metadata suite. It must
stay bounded and must not invoke the full strict chain indirectly.

`verify-all` is the canonical exhaustive local gate: it builds the default
native graph, runs all CTest and Python tests, then runs every strict validator.
It is intentionally slower and is required before a WorkUnit closeout; a green
fast run does not replace it.

The affected map is `contracts/policy/test_impact.v1.json`. It selects focused
native targets, Python modules, strict validators, and platform package lanes.
Inventory floors detect test removal, but passing affected validation does not
replace Debug/Release, sanitizer, fuzz, coverage, ABI, package, or target-CI
promotion evidence.

Performance baselines are advisory on shared machines. Use
`tools/benchmark.py --compare`; reserve `--enforce` for a stable dedicated
runner. See `docs/architecture/test-architecture-and-native-quality.v1.md`.
