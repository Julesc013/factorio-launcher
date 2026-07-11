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
- FacMan Python: PASS (188/188).
- Strict and AIDE Lite tests: PASS.
- Dependency-lock validator and admission tests: PASS (4/4).
- Normal deflate archive full validation and streaming extraction: PASS.
- Forced tiny ZIP64 write, detection, stat, and extraction: PASS.
- AIDE changed-file verification: PASS after task-scope reconciliation.
