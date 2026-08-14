# Windows preview prequalification checkpoint

## Scope

This D1 checkpoint keeps useful work moving while ULK #16 and the stacked
FacMan integration train remain protected human or independently delegated D2
gates. It adds a deterministic qualification runner and records a synthetic
integration rehearsal. It does not change either provider pin, qualify a
package, authorize Factorio execution, mutate Setup, or grant release
authority.

## Exact topology

- WorkUnit: `FACMAN-WINDOWS-PREVIEW-PREQUALIFICATION-01`.
- branch: `task/facman-windows-preview-prequalification-01`.
- exact stacked base: PR #157 head
  `a67aea12fdc5eb8882a48f5b3bb84aa2cca1b56f`.
- obligation-factory implementation:
  `e5c3021c3c3742c44c3123c0ec141183af1df3ca`, tree
  `ca6e2a2a6c22f30f84023af943383abef1a5f2e4`.
- canonical FacMan `dev` observed at start:
  `27991db20779f6eb89262be4ce52f7f68209747d`.
- canonical ULK `main` observed at start:
  `09f0639ab6529fba2f2aa22e9bf68e5eebed0553`.
- repaired-provider canary: ULK #16 head
  `7babf28bcda41186704868417743c39464a84e65`, tree
  `552cff5204ddc70dca57e979bf88e86c85a23140`.
- canonical USK remains
  `32488fc13bd2439f9f6e52e83a97f6da345a7650`.

The autonomy policy remains activation-pending. Protected writes,
self-approval, self-merge, Factorio execution, Setup mutation, signing, and
publication therefore remain false.

## Deterministic obligation factory

`tools/preview_obligation_factory.py` reads the release compiler rather than a
second hand-maintained obligation list. Its registry must exactly match the
compiler-resolved set before any command runs. For each obligation it records:

- the exact command and required input paths;
- source commit, tree, clean-state, provider class, and build identity;
- release-resolution digest and qualification state;
- result, duration, evidence filename, and evidence SHA-256;
- a bounded blocked/failure classification; and
- source paths whose changes invalidate the receipt.

The output is validated against
`facman.preview_obligation_ledger.v1`. Every authority field is structurally
false. A repaired-provider canary fails closed for package-custody obligations
even when package paths are supplied; only the canonical provider composition
may satisfy those rows.

## Exact clean-source result

Against implementation commit `e5c3021c` and the synthetic repaired-provider
build, the factory resolved exactly 23 obligations:

```text
pass       15
fail        0
blocked     8
planned     0
```

The eight blocked rows are:

```text
forbidden_payload_scan
package_adapter_round_trip
package_relocation_smoke
package_reproducibility_proof
package_runtime_smoke
windows_linkage_check
winforms_backend_identity_check
zip_structure_check
```

Each is classified `canonical_provider_identity_pending`. This is a custody
gate, not a test failure. The exact out-of-tree ledger SHA-256 is
`cbacce031984ff4c591e625db0993e240a2d496fc320ddf008b0c4d08580e285`.
The resolved qualification-plan digest is
`8934b386750cb56afda0fb1337e2ffa29c0a5fe009811364cce8c9a1455b421b`
and remains `qualified = false`.

## ULK repair assurance

The exact #16 provider head was rebuilt independently. Local proof passed:

- 19/19 Python tests;
- 15/15 native CTest cases;
- installed static, shared, and combined SDK qualification; and
- strict validation.

Source inspection additionally confirmed legacy V1 reads, V2 writes, CRC
coverage of `commit_order`, preservation of admission order across idempotent
updates, deterministic mixed V1/V2 selection, lock serialization, and explicit
commit-order exhaustion refusal. This checkpoint does not claim broader ULK
process execution or provider SPI maturity.

## Synthetic full-stack rehearsal

A local, disposable worktree normally merged the exact histories in order:

```text
dev@27991db2
  -> #154@6694eca0
  -> #155@31aa0f1b
  -> #156@a137c2e0
  -> #157@a67aea12
```

There were no merge or generated-state conflicts. The local rehearsal commit
is `d57bfc04626b4b9f8f562c194e470a97993db4b4`, tree
`90b666b3bbd84ca6a93f981c15bc2281ab018b2d`. It is evidence only and is not a
prediction of any protected merge SHA.

Against ULK #16 and the unchanged canonical USK, the rehearsal passed 44/44
native tests. The full Python promotion census ran 1,015 tests and deliberately
refused mixed canonical/canary package identity, an absent shared WinForms
package root, and the stale canonical-state assertion. Those negative controls
were retained; no identity or custody check was weakened.

## Terminal and Windows shell receipt

Focused execution against the repaired-provider rehearsal passed 16/16 tests,
including:

- live Windows ConPTY navigation, resize, fallback, cancellation, and terminal
  restoration;
- ordinary TUI, linear, redirected, unavailable, and transport-refusal paths;
- TUI performance and screen-reader-oriented transcript receipts;
- one-binary CLI/RPC/TUI routing;
- compiled WinForms keyboard navigation and close-is-not-cancel behavior; and
- UI Automation, system-colour, minimum-layout, Unicode identity, and
  100%-200% scale engineering checks.

These are automated engineering receipts. They do not replace a human
screen-reader, High Contrast, or usability verdict on the frozen candidate.

## Stop boundary and next work

The normal package pipeline correctly refuses canary provider identity.
Creating a ZIP by bypassing that refusal would not be a candidate receipt.
The maximum truthful state is therefore source/runtime prequalification with
eight package rows blocked.

Next, in dependency order:

1. independently integrate ULK #16 and verify its protected `main` head;
2. integrate FacMan #154, normally restack and qualify #155-#157;
3. adopt the exact repaired canonical ULK `main` merge identity in FacMan;
4. rebuild this WorkUnit on the resulting exact `dev` and rerun all 23 rows;
5. construct two byte-identical internal candidate packages; and
6. freeze the human test packet only after exact package qualification.

## Authority and no-effect audit

- real Factorio execution: false;
- production launch executor: absent;
- Setup mutation: false;
- tracked provider lock mutation: none;
- protected branch write or merge: none;
- private archive access: none;
- foreign installation mutation: none;
- signing, tags, releases, publication, and support promotion: none.
