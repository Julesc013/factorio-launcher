# Validation

Result: PASS for the revision-pinned R3.3 core and Stretches A-C.

- Core implementation `93edfdc5`: CI `29156543059` green.
- Core checkpoint `d8768ff`: CI `29156897355` and security `29156897356` green.
- Stretch A implementation `df6d8b08`: CI `29157471842` and security
  `29157471908` green.
- Stretch B final implementation `4819b9d1`: CI `29158246484` and security
  `29158246490` green.
- Stretch C final implementation `6dcdf74f`: CI `29159257155`, schema
  `29159257150`, and security `29159257159` green.
- Stretch C target matrix: Linux, Windows/package, macOS archive, macOS native
  CLI/package, and AppKit compile-only all green.
- Final macOS job: native CTest 9/9, portable Python 226/226, strict checks,
  zero-skip package proof, and artifact upload all green.
- Final local Windows selected package: integrity/runtime pass, 168 files,
  unsigned provenance pass.

Failed attempts `29158844890`, `29158980502`, and `29159016898`, plus the
superseded path-bearing artifact from `29159110943`, remain recorded in the
Stretch C evidence. No failure was hidden or converted into success.
