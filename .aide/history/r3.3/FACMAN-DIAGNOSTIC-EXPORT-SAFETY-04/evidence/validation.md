# Validation

Result: PASS, including exact-SHA cross-platform CI.

## Behavior proven locally

- `diagnostics.export` routes through the registered ULK descriptor, FLB, and
  typed FacMan operation. `doctor --diagnostic-bundle` is a CLI alias into the
  same route.
- Windows sources use wide stable handles with reparse, containment, volume,
  file-ID, link-count, sharing, size, attribute, and timestamp checks. POSIX
  sources use anchored `openat`, `O_NOFOLLOW`, and before/after `fstat` checks.
- Only reviewed manifests, config files, Factorio logs, and explicit text
  diagnostics are collected. Unknown/archive formats are omitted; malformed
  structured input, binary content under a reviewed name, hardlinks, source
  races, and remaining private absolute paths refuse.
- The typed bundle contains traversal, redaction, file-read consistency, and
  omission reports plus pseudonymous source identity and file hash closure.
- Output uses deterministic production deflate, owned destination-volume
  staging, no-clobber commit, the bounded transaction journal, and final ZIP
  manifest/entry-count self-verification.
- Fault injection covers all ten success states. Pre-commit faults leave no
  target; post-commit faults leave a complete recoverable ZIP. Explicit
  recovery preserves the ZIP and removes only recognized owned staging.
- Source fixtures and instance files remain unchanged. No required test was
  skipped.

## Local gates

- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (216/216, zero skips).
- Strict checks: PASS (23 commands, 59 schemas, 89 refusal codes, 27 refusal
  goldens).
- Diagnostic export and transaction recovery checkers: PASS.
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## Exact-SHA CI

- FacMan revision: `069cf22c14fa903357411ede32f23b88676b6214`.
- CI run `29155497880`: PASS.
  - Linux native and ASan/UBSan archive corpus/fuzz: PASS.
  - Windows native, complete Python suite, WinForms build/client smoke,
    zero-skip package proof, selected package integrity/relocation, and legacy
    compatibility package: PASS.
  - macOS archive native smoke: PASS.
  - AppKit compile-only: PASS.
- Schema run `29155497897`: PASS.
- Security-policy run `29155497871`: PASS.

The preceding governance-only activation run `29154499018` failed Linux and
Windows Python truth checks because the required Windows-discovery sentence was
line-wrapped across the exact checker anchor. The implementation revision
restored that literal truth statement and passed the complete replacement
matrix; the failed activation run is not cited as product evidence.

## Authority boundary

The promoted path is limited to reviewed local formats and supported local
filesystems through the CLI and doctor CLI alias. Native GUI export UX,
arbitrary files, shared/network filesystems, `run.execute`, real Factorio
isolation, Safe beta, setup mutation, networking, credentials, signing,
tagging, release, and publication remain unpromoted.
