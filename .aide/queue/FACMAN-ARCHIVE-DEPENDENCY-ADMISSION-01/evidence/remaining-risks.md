# Remaining Risks

- Miniz 3.1.2 rejects its own deliberately forced tiny ZIP64 archive in
  `mz_zip_validate_file`, despite successfully writing, detecting, inspecting,
  and extracting it. WorkUnit 2 must independently validate ZIP64 local and
  central metadata before consumer migration; this is not waived.
- Miniz exposes archive mechanisms, not FacMan path safety, collision policy,
  resource budgets, transactional extraction, or deterministic product
  semantics. Those remain WorkUnit 2 responsibilities.
- Encryption is unsupported and must be detected and refused.
- No archive consumer uses Miniz yet.
