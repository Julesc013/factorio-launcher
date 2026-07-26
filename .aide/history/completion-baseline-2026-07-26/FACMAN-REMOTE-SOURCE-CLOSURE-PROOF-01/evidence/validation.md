# Validation

Result: `PASS`

Observed at: `2026-07-26T10:59:47Z`

Machine evidence:

- `docs/quality/evidence/source-closure/remote-source-closure.v1.json`
- schema: `facman.remote_source_closure.v1`
- claim: `remote_source_closure_proven`
- recorded validation steps: `19`, all PASS

Exact remote checkouts:

- FacMan: `1d94fcfc567b3ffe8d7d7dc3829cc7984147b3a7`
- Universal Launcher: `fbb0cc87a14e8e4b26d74088a791dc83ebd4337d`
- Universal Setup: `3f8489275077347c2918f3bb03614ec6431362ff`
- all three pins remotely fetchable from their required refs
- all three pins ancestors of their required refs
- all three checkouts detached, exact, clean, and without alternates
- final source worktrees clean after validation

Fresh build and test results:

- Universal Launcher native: `4`
- Universal Setup native: `16`
- FacMan native: `53`
- FacMan Python: `501`
- FacMan required Windows package tests: `14`
- required package skips: `0`
- installed SDK proof: PASS
- Universal Launcher strict: PASS
- Universal Setup strict: PASS
- FacMan strict: PASS
- FacMan AIDE Lite: PASS

Package evidence:

- profile: `windows_portable_cli_x64`
- files: `482`
- artifact:
  `facman-0.1.0-dev.contract-windows-cli-x64-portable.zip`
- artifact SHA-256:
  `2fd6b62e5f0b8bd1a5800652b22434d8a6a955733958e6b17cb7ab26391e4cfe`
- provenance SHA-256:
  `63d37522f9cff50ccc4eaffdc9faa11633fb2f1673387eed5c37d734323dd3c3`
- package runtime smoke: PASS
- archived package runtime smoke: PASS
- provenance verification: PASS
- packaged source revisions equal the three exact proof checkouts

Local implementation validation before publication:

- `python -B -m unittest discover -s tests -v`: PASS
- `python -B tools/strict_check.py`: PASS
- `python .aide/scripts/aide_lite.py test`: PASS
- focused source-closure tests: PASS (`18` tests)
- schema validation: PASS (`296` schemas)
- commit-message validation: PASS
- diff hygiene: PASS

Claim boundary:

- Factorio execution: `false`
- permit issuance: `false`
- authority promotion: `false`
- package publication: `false`
