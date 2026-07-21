# Gate 2 remaining risks and explicit non-claims

## Required before Gate 2 closeout

- Hosted Linux GCC, macOS AppleClang, Windows MSVC, sanitizer, CodeQL, schema,
  code-security, and security-policy checks must pass for the exact reviewed
  task head.
- The reviewed head must merge to `dev`, and the exact merged `dev` revision
  must pass the required post-merge checks and clean pinned three-repository
  reconstruction before this WorkUnit is closed.
- Generated truth and claim-ledger state must be updated in a separate honest
  closeout transition after integration evidence exists.

## Deliberate Gate 2 limits

- `factorio.instance.v1` remains the persisted compatibility record;
  `InstanceSpec`, `InstanceBinding`, `InstanceReadiness`, and `InstanceView` are
  computed projections, not a migrated workspace model.
- Only `menu` readiness is implemented. Other registered launch intents are
  represented but refused with `unsupported_launch_intent`.
- Overall readiness remains blocked because OperationPermit issuance and real
  Factorio execution do not exist. No real product was launched or reviewed.
- Per-operation executable, filesystem, process, isolation, account, and
  entitlement evidence remains unknown or degraded and must be revalidated by
  later providers.
- Account and credential fields are conservative logical absence; no
  credential provider is implemented or accessed.
- Preset, multi-profile, advanced resource, server, scenario, blueprint, and
  save-compatibility fields remain target architecture beyond the minimal
  legacy compatibility projection.
- Modset satisfaction uses the existing exact local lock verifier. An unlocked
  mod directory is visible but degraded and does not become portable intent.
- Readiness is evidence and explanation only. It is not a capability token,
  permit, cached authority flag, preparation plan, or promise that a later
  launch will succeed.

## Authority and release non-claims

This work does not promote installation apply, instance preparation, process
execution, network, credential, registry, elevation, Setup apply, signing,
publication, Safe beta, `main`, or release authority. Steam and foreign
installations remain externally owned/read-only under their existing policy.
