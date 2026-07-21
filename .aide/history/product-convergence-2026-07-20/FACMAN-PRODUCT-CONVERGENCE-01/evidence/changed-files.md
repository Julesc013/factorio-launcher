# Changed Files

- `release/index/project_status.v2.toml` is the canonical current product
  source. It now selects product convergence, the Play-driven sequence, two
  independent execution modes, separate readiness dimensions, and M3 as
  post-alpha backlog while preserving historical M1/M2/H1 records.
- `tools/project_state.py` generates README, roadmap, release, JSON, concise
  AIDE memory, and a contributor `--summary` command from canonical inputs.
- `contracts/policy/capabilities.v1.toml` and `effects.v1.toml` define and
  validate durable capabilities and effects independently of milestone and
  command spellings.
- `docs/product/master_plan.md` and `product_vision.md` freeze the charter,
  golden journey, repository train, execution guarantees, compatibility,
  testing, delivery order, and refactor ceiling.
- `.aide/profile.yaml`, target memory, queue state, and immutable history now
  select the current product objective without deleting historical evidence.
- Runtime status, capabilities, launch notes, setup refusals, and refusal-law
  messages use durable product/capability language rather than M2/H1 wording.
- `CMakeLists.txt`, `apps/cli/CMakeLists.txt`, and the CLI version path expose
  source revision and build configuration.
- `tools/dev.py` and `test_impact.v1.json` make the canonical fast command
  build only fast-labelled targets and avoid indirectly invoking the full
  strict suite; `verify-all` remains exhaustive.
- Focused native/Python assertions and the new capability-policy validator
  enforce the changed truth and prevent vocabulary drift.

No real Factorio process, network service, credential provider, setup apply,
signing service, publication channel, or external user installation was used.
