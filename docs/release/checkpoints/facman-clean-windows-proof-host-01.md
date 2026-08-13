# FacMan clean Windows proof-host preparation 01

Date: 13 August 2026

State: `implementation_ready_specification_only`

## Exact scope

```text
repository  Julesc013/factorio-launcher
base        dev@54b188c0b2d4ab62c1d948cd1c548489fbe8c8b7
WorkUnit    FACMAN-CLEAN-WINDOWS-PROOF-HOST-01
authority   planning and non-executing validation only
```

The existing route dossier remains current: Factorio 2.0.77 is the sole defined
future execution-route candidate, while 2.1.14 remains archive/materialization
evidence. No new route fact was found, so the dossier was not rewritten and no
route was activated.

The new `clean_windows_proof_host.v1` architecture record makes provisioning
implementation-ready. It specifies a discard-on-reset host, exact OS/boot/
toolchain/source/package/route identities, a non-administrator execution epoch,
read-only private-input injection, bootstrap-network closure, observer and
negative-control prerequisites, bounded redaction, digest-only export, and
post-run clone destruction.

## Gate remaining

This record is not host evidence. A later authorized implementation must create
the actual restorable host and pass its synthetic-input acceptance suite. Only
then may an owner separately authorize the exact private archive and real-Play
route.

## No-effect audit

No protected ref, provider pin, route, Factorio archive, Factorio installation,
Factorio process, Setup state, signing key, credential, tag, release,
publication, or support classification was read or changed. No infrastructure
was provisioned.

## Dependency order

1. Human-review the clean-host specification.
2. Provision the resettable host and run synthetic negative controls.
3. Accept one exact route-version decision and immutable private-input digest.
4. Separately authorize the real-Play run.
5. Qualify only the exact candidate tuple and complete the human receipt.
6. Continue beta/RC, signing-policy, publication, and support gates.
