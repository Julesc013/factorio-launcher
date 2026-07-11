# Validation

Result: PASS locally; exact-SHA cross-platform CI is pending the WorkUnit
commit and push.

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

## Authority boundary

The promoted path is limited to reviewed local formats and supported local
filesystems through the CLI and doctor CLI alias. Native GUI export UX,
arbitrary files, shared/network filesystems, `run.execute`, real Factorio
isolation, Safe beta, setup mutation, networking, credentials, signing,
tagging, release, and publication remain unpromoted.
