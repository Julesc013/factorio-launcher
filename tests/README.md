# Tests

Owns proof for the repository.

May contain:

- unit tests
- integration tests
- contract tests
- golden outputs
- fake fixtures
- black-box native CLI tests

Must not contain real Factorio binaries, credentials, or user state.

Alpha command-surface goldens are checked with:

```powershell
py -3 tools/alpha_vertical_slice_check.py
```

Those goldens are stable contract-shaped examples for the current vertical slice;
they do not replace end-to-end CLI behavior tests.

The canonical developer interface is:

```powershell
py -3 tools/dev.py test --affected
py -3 tools/dev.py test --fast
py -3 tools/dev.py test --full
py -3 tools/dev.py verify-all
```

Test categories and module impact routing are defined in
`contracts/policy/test_impact.v1.json`. Operator acceptance is deliberately
manual and cannot be passed by the developer tool.
