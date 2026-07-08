# Launch

Launch profile expansion, preflight checks, command construction, and post-run
indexing.

Current implementation:

- `flb_factorio_launch_plan.*` builds the isolated launch arguments and
  `factorio.launch_plan.v1` JSON used by the native CLI vertical slice.
- `apps/cli/` loads install and instance refs, then delegates launch-plan
  construction here instead of owning the product launch schema directly.
- Process execution and preflight enforcement are still the next hardening
  target; this module currently preserves the dry-run-first launch-plan shape.
