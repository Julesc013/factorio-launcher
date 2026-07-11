# Validation

Result: PASS for the revision-pinned R3.3 core; closeout revision CI pending.

- FacMan implementation revision:
  `93edfdc59865e4a07f261bdabb61c6e2db6d0f99`.
- FacMan CI `29156543059`: PASS across Linux native/package/sanitizers,
  Windows native/package/WinForms, macOS archive, and AppKit compile-only.
- Linux and Windows complete Python suites: PASS (221/221 each).
- Linux and Windows CTest: PASS (9/9 each).
- Windows required package proof: PASS (13/13, zero skips).
- Linux required package proof: PASS (zero skips, 14 named checks).
- Security `29156543070`: PASS.
- Schema `29156192783`: PASS; final-sha Linux/Windows strict repeated 61 schemas.
- Universal Launcher `29146647390`: PASS including native build and CTest 1/1.
- Universal Setup `29146653792`: PASS including native build and CTest 2/2.
- Local selected Windows artifact build, 161-file integrity verification,
  pathless runtime smoke, and relocation: PASS.
- Dependency revisions, workspace contract, AIDE Lite, strict, source format,
  commit policy, and diff checks: PASS.

The closeout changes only governance, claims, and evidence. Its own exact SHA
must pass the repository workflows before any stretch WorkUnit begins.
