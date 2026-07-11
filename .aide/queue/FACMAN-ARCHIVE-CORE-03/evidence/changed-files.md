# Changed Files

- `runtime/archive/`: production archive API, platform I/O and owned staging,
  path/resource policy, independent metadata parser, streamed CRC reader,
  extraction planner, and staged deterministic writer.
- `external/miniz/`: unchanged admitted compression mechanism.
- `CMakeLists.txt`: archive library, native proofs, fuzz harnesses, and optional
  ASan/UBSan build mode.
- `tests/native/fl_archive_*.cpp`: native stored/deflate/ZIP64, deterministic
  writer, extraction cleanup, metadata fuzz, and extraction-planning fuzz
  executables.
- `tests/test_archive_core.py`: malicious corpus, resource budgets, property
  generation, deterministic mutations, and fuzz orchestration.
- `tools/archive_core_check.py`, `tools/strict_check.py`, and
  `tools/structure_policy_check.py`: production-core structure and legacy
  parser location enforcement.
- `.github/workflows/ci.yml`: Linux ASan/UBSan archive corpus and macOS archive
  native smoke jobs.
- `.aide/queue/FACMAN-ARCHIVE-CORE-03/`: bounded scope and evidence.
