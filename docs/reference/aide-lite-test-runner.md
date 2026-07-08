# AIDE Lite Test Runner

## Purpose

QFIX-02 makes AIDE Lite validation boring on purpose. Future agents should not
need to remember Python `unittest` import rules for a hidden `.aide/` directory
before they can trust the token-survival substrate.

## Canonical Command

Run this from the repository root:

```bash
py -3 .aide/scripts/aide_lite.py test
```

Use `python` or `python3` only when the Windows launcher is unavailable.

The command runs the existing internal AIDE Lite selftest checks, prints
PASS/FAIL output, returns nonzero on failure, writes no committed repo state,
and makes no provider, model, or network calls.

`selftest` remains supported:

```bash
py -3 .aide/scripts/aide_lite.py selftest
```

## Raw Unit Tests

The supported raw unittest discovery command is:

```bash
py -3 -m unittest discover -s .aide/scripts/tests
```

QFIX-02 verified this command passes.

## Non-Canonical Command

Do not use:

```bash
py -3 -m unittest discover -s .aide/scripts/tests -t .
```

With `-t .`, `unittest` requires `.aide/scripts/tests` to be importable as a
package path from the repo root. `.aide/` is a hidden committed contract
directory, not a Python package namespace, so that form fails before loading
tests. Adding `__init__.py` files would not be the right fix because it would
blur the `.aide/` contract boundary.

## Cross-Repo Implication

Q21 Cross-Repo Pack Export / Import v0 can now rely on one obvious local command
when evaluating copied AIDE Lite packs:

```bash
py -3 .aide/scripts/aide_lite.py test
```

The command is stdlib-only and no-call, so it is safe to run before any future
Gateway/provider/runtime work.
