# Remaining risks

- Hosted Linux, macOS, Windows package, coverage, schema, policy, and security
  lanes must pass against the exact published commit before this WorkUnit
  closes.
- This repair deliberately does not generate or enforce the final build and
  development identity. That remains
  `FACMAN-BUILD-AND-DEVELOPMENT-TRUTH-01`.
- Durable operation identifiers, cancellation-after-dispatch outcomes, and
  recovery inspection remain
  `FACMAN-TRANSPORT-OUTCOME-SEMANTICS-01`.
- Product runtime and verdict/evidence orchestration remain coupled until
  `FACMAN-PLAY-CANDIDATE-RUNTIME-SEPARATION-01`.
- Directly imported installations now expose their honest `unknown` lifecycle.
  A later reviewed verification/refresh flow must produce exact active evidence;
  no compatibility fallback restores inferred activity.
- No Play candidate was rebuilt or qualified, no Factorio process was started,
  and no prior verdict evidence became current.
