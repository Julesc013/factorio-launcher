# Factorio Version Capability Corpus

This operator tool builds sanitized compatibility evidence from locally held
Factorio versions without importing, repairing, updating, or launching a game.
It invokes only `--version` and `--help`, redirects user-data environment roots
to a temporary sandbox, and compares each install tree before and after.

Run the bounded Windows corpus with:

```powershell
py -3 tools/factorio_version_capability_corpus.py `
  --root D:\Games\Factorio `
  --expected 0.6 0.7 0.8 0.9 0.10 0.11 0.12 0.13 0.14 0.15 0.16 0.17 1.0 1.1 2.0 2.1
```

The report is written to ignored local state at
`.aide/local/evidence/factorio-version-capability-corpus.v1.json`. It contains
relative executable paths, executable digests, parsed version numbers,
capability booleans, probe status, platform-integration classification, and
install-tree fingerprints. It never persists raw process output, absolute
paths, account identifiers, credentials, or proprietary binaries.

`complete` means every expected directory was present, a Factorio executable
was found, and every install tree remained unchanged. It does not mean strict
isolation passed. `none_detected` is not proof of no platform integration, and
all non-Steam versions remain `unproven` until a separately reviewed H1 result.
