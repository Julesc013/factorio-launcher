# Capability Reality Ledger

X-OS-02 adds a report-only capability reality ledger for AIDE Task OS. It classifies source-repository evidence into controlled capability states without treating docs, fixtures, dry-runs, no-call metadata, release drafts, or target-specific notes as live product behavior.

## Command Surface

- `py -3 .aide/scripts/aide_lite.py capability status`
- `py -3 .aide/scripts/aide_lite.py capability scan`
- `py -3 .aide/scripts/aide_lite.py capability ledger`
- `py -3 .aide/scripts/aide_lite.py capability overclaim-report`
- `py -3 .aide/scripts/aide_lite.py capability validate`

## Source Contracts

- `.aide/policies/capability-reality.yaml`: controlled states, evidence classes, modifiers, overclaim classes, and proof rules.
- `.aide/capabilities/capability-seeds.yaml`: current conservative seed records.
- `.aide/capabilities/capability-observation.schema.json`: generated observation report shape.
- `.aide/capabilities/capability-overclaim.schema.json`: generated overclaim report shape.
- `.aide/ledgers/capability-ledger.schema.json`: generated capability ledger shape.

## Generated Reports

- `.aide/reports/capability-command-status.md`
- `.aide/reports/capability-observations.json`
- `.aide/reports/capability-observations.md`
- `.aide/reports/capability-ledger.json`
- `.aide/reports/capability-ledger.md`
- `.aide/reports/capability-overclaims.json`
- `.aide/reports/capability-overclaims.md`
- `.aide/reports/capability-validation.md`

## States

Capability records use `planned`, `specified`, `stubbed`, `implemented`, `tested`, `exposed`, `documented`, `deprecated`, `removed`, and `unknown`.

The dominant state is intentionally conservative. Additional observed states can appear when evidence also contains docs, schemas, tests, command surfaces, or generated reports, but those observations do not promote a capability beyond the dominant state.

## Overclaim Rules

The ledger keeps these boundaries explicit:

- docs-only evidence is not implementation proof
- fixture-only evidence is not production behavior
- report-only commands are not apply behavior
- no-call provider metadata is not live provider integration
- release drafts are not publication
- dry-runs are not install, repair, upgrade, rollback, uninstall, or transaction apply
- source-generated state is not target truth
- target-pilot evidence is not product-general availability
- unknown state is not verified state

## Boundary

X-OS-02 does not execute tasks, repairs, branches, targets, releases, providers, models, network calls, schedulers, workers, Runtime, Hosts, Commander, Mobile, Gateway forwarding, MCP/A2A, UI, or app-surface behavior. Generated capability reports are source-side evidence only. Target repositories must generate their own capability reality evidence after import.
