# Validation

Result: PASS with one recorded upstream limitation assigned to WorkUnit 2.

- Official release: Miniz 3.1.2, commit
  `77d0dce8627735138c51770d1799a1ef48f2117d`.
- Official and locally computed release asset SHA-256:
  `f0446d863f9c19926ad9483c523fdc42e42b8d4a6a431d27e09d49c79a140d9a`.
- License: MIT; source and binary notice obligations recorded.
- Runtime transitive dependencies: none.
- Runtime networking: none.
- Native fresh build: PASS.
- Native CTest: PASS (8/8), including Miniz static capability smoke.
- FacMan Python: PASS (189/189 after the standalone CI repair).
- Strict and AIDE Lite tests: PASS.
- Dependency-lock validator and admission tests: PASS (4/4).
- Normal deflate archive full validation and streaming extraction: PASS.
- Forced tiny ZIP64 write, detection, stat, and extraction: PASS.
- AIDE changed-file verification: PASS after task-scope reconciliation.

## Standalone CI repair

The first exact-SHA workflow run `29150433398` exposed two admission defects.
Git had normalized the extensionless upstream `LICENSE` blob to LF while a
Windows worktree restored CRLF. The admission test intentionally checks the
reviewed upstream digest, so Linux correctly failed that mismatch. The file is
now explicitly binary in `.gitattributes`, preserving the reviewed 1,184-byte
upstream file and SHA-256 on every platform. The strict source-format checker
also applied FacMan line-length policy to exact upstream files; it now excludes
only the admitted `external/miniz/` tree, with a regression proving the scope
does not cover other external or first-party paths. These are provenance and
policy repairs; dependency code and runtime behavior did not change.
