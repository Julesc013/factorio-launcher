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

Exact revision `1b5ec68468c6ea09ef6d615ae8819b38e641d3af` reached every
Linux baseline gate, including native tests, the sanitizer archive corpus and
fuzz proof, Python, strict checks, and compatibility packages, but failed the
new package-proof step in run `29156193096`. The mutation fixture named a
documentation file excluded by the intentionally minimal Linux payload. The
repair targets the packaged `docs/release/PACKAGE_LAYOUT.md`; it does not
weaken or skip the modified-payload refusal.

## Authority boundary

The package remains unsigned and unpublished. This WorkUnit does not execute
Factorio and does not enable `run.execute`, real Factorio isolation, Safe beta,
setup mutation, networking, credentials, dynamic plugins, signing, tagging,
release creation, or publication.
