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
