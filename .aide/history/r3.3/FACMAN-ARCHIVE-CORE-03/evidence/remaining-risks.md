# Remaining Risks

- No production archive-core claim is promoted while this WorkUnit is active.
- Existing CLI consumers still use their legacy archive code until separate
  parity and route migrations pass.
- The admitted Miniz tiny forced-ZIP64 validator limitation requires FacMan's
  independent central-directory and local-header agreement proof; that parser
  is locally green but still awaits sanitizer and macOS CI.
- Stable source identity across a complete consumer operation and durable final
  target commits belong to the later transfer and transaction WorkUnits.
- Unicode normalization collision detection deliberately covers the declared
  Latin canonical-composition set used by current product filenames; broader
  scripts are case-folded and UTF-8 validated but are not claimed as complete
  Unicode normalization without a future reviewed normalization dependency.
