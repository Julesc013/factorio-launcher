# Validation

Result: LOCAL PASS; exact-SHA sanitizer and cross-platform CI pending.

## Production behavior proven locally

- Stored and deflate entries stream through Miniz and verify expanded size and
  CRC.
- Classic ZIP, forced tiny ZIP64, local/central agreement, ZIP64 extras, and
  signed or unsigned 32/64-bit descriptors are parsed independently.
- Truncated, multi-disk, encrypted, malformed-extra, mismatched, overlapping,
  and CRC-damaged archives refuse.
- Absolute, drive, UNC/backslash, traversal, dot/empty segment, ADS, Windows
  reserved, symlink, device, FIFO, socket, duplicate, case-colliding,
  normalization-colliding, and file/directory-colliding entries refuse.
- Archive, entry-count, compressed, expanded, total-expanded, ratio, path,
  depth, and elapsed-time budgets refuse before output.
- Stored/deflate output is streamed in deterministic path order to a new owned
  staging root, byte-capped during creation, and self-inspected before success.
- Forced ZIP64 output and spaces, Unicode, empty files/directories, and Windows
  long paths pass.
- Failed extraction removes its recognized owned staging root.

## Local gates

- Fresh CMake configure and full native build: PASS.
- Native CTest: PASS (9/9).
- Archive adversarial/property/mutation suite: PASS (7/7).
- Complete FacMan Python suite: PASS (196/196).
- Strict checks, including archive-core and structure policy: PASS.
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## CI-only gates

- First exact-SHA run `29151465751`: Linux sanitizer/native PASS, AppKit PASS,
  Windows/package PASS, macOS archive build PASS, macOS archive smoke FAIL with
  native CTest exit 8 and no public step log. The smoke previously placed its
  long-path tree under the platform temporary directory; that can traverse the
  macOS temporary-root alias rejected by the core's no-link source policy. The
  harness now uses the checkout-owned current directory without relaxing
  runtime policy, and emits its internal stage code as a workflow annotation if
  another failure occurs. Replacement exact-SHA CI is required.
- Linux ASan/UBSan archive smoke, adversarial corpus, and both fuzz harnesses:
  PENDING exact-SHA workflow. The installed WSL environment has Python but no
  C/C++ compiler or CMake, so this proof is not represented as local.
- macOS archive-core compile and native smoke: PENDING exact-SHA workflow.
- Windows/package, Linux native/package compatibility, AppKit compile, schema,
  and security regression lanes: PENDING exact-SHA workflow.

## Authority boundary

The legacy CLI and Factorio mod stored-only parsers remain in their two
machine-checked locations. No consumer calls the new core until later parity
WorkUnits. No command, diagnostic export, `run.execute`, or release capability
is promoted by this WorkUnit.
