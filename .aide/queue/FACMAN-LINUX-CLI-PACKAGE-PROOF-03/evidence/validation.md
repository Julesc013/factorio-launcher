# Validation

Result: LOCAL GATES PASS; TARGET LINUX PACKAGE PROOF PENDING EXACT-SHA CI.

## Local proof

- Full native Windows build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (220/220, zero skips).
- Strict checks: PASS (23 commands, 61 schemas, 89 refusal codes, 27 refusal
  goldens, 7 release profiles, 7 package skeletons).
- Linux proof contract/static tests: PASS (3/3).
- AIDE Lite portable validation: PASS.
- AIDE changed-file verification: PASS (37/37 in scope at review time).
- Source format and `git diff --check`: PASS.

## Target gate

The Linux proof driver deliberately refuses this Windows host. The exact
implementation revision must pass `linux-native` on the declared Ubuntu 24.04
x64 runner before ELF, glibc, dependency, tarball extraction, relocation,
read-only-root, or Linux runtime claims are promoted. The target run must have
zero required skips and emit a schema-valid evidence document plus the exact
artifact SHA-256.

## Authority boundary

The package remains unsigned and unpublished. This WorkUnit does not execute
Factorio and does not enable `run.execute`, real Factorio isolation, Safe beta,
setup mutation, networking, credentials, dynamic plugins, signing, tagging,
release creation, or publication.
