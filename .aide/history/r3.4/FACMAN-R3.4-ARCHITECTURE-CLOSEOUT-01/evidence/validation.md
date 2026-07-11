# FACMAN-R3.4-ARCHITECTURE-CLOSEOUT-01 validation

Result: WARN. Local Windows and three-repository proof is green; Linux and
macOS promotion is held for declared target runners.

## Pinned revisions

- FacMan: `eaaed196b9535729a02261c8fec72de5996be509`.
- Universal Launcher: `80a848375227dc858865874ef594c4b466877241`.
- Universal Setup: `4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`.

## Passed locally

- ULK: native 1/1, Python 4/4, strict PASS.
- USK: native 2/2, Python 9/9, strict PASS.
- FacMan: Debug 16/16 CTests; Release 16/16 CTests.
- Portable Python: 249/249.
- Required Windows package: 14/14, zero skips.
- Archive corpus: 7/7.
- WinForms: zero-warning build and command-client smoke PASS.
- GCC 15 full source compile with `-Werror`: PASS.
- Strict checks, AIDE portable suite, dependency pins, and structured commit
  range: PASS.
- Two package stages reproduced SHA-256
  `6cab44c5d8f99e5d749d849b827154bda50da3b2ed2d68bffe290102a503b77f`.

## Not run

- Ubuntu ASan/UBSan, libFuzzer, clang-tidy, coverage, and package proof.
- macOS Intel native/package proof and AppKit compile proof.

These are recorded in `FACMAN-R3.4-TARGET-RUNNER-PROMOTION-01`; they are not
converted into local PASS results. No external push was authorized.

The detailed artifact, SBOM, provenance, benchmark, and limitation record is
`docs/release/checkpoints/r3.4-architecture-consolidation.md`.
