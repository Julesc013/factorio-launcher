# Evolution spine constitution

Status: ratified planning law; post-C1; non-authorizing

Last reviewed: 2026-08-10

## Purpose

FacMan, Universal Launcher, and Universal Setup use one evolution law:

> Evolution-proof architecture means stable meaning, independently versioned
> contracts, replaceable implementations, reversible state transitions,
> bounded extensions, truthful support claims, and reconstructible releases.

This law completes the architectural direction without adding a repository,
merging provider and product histories, replacing the product-owned compiler,
or widening the current C1 route. It prepares later contracts and validators;
it does not implement or authorize their effects.

## Current C1 boundary

The active sequence remains:

```text
source/static/shared/relocated/private-runtime conformance
-> explicit provider consumption modes
-> one evidence-selected provider reconciliation
-> non-authorizing successor route definition v2 if required
-> merge accepted dev forward into the unchanged source-closure line
-> task-ref and canonical source closure
-> successor qualification
-> separately authorized two-launch human verdict
-> one exact route promotion after Pass
-> Windows C1 package and clean-machine qualification
```

The evolution spine is not a dependency of those steps. C1 is the internal
alpha foundation, not public `0.1.0`. Its canonical WorkUnits remain in the
later horizon until the C1 foundation is evidence-complete.

## Repository and authority law

Permanent ownership remains:

| Repository or layer | Meaning |
| --- | --- |
| Universal Launcher / **ULK** | Product-neutral runnable references, plans, operations, outcomes and command/Setup-handoff law: the semantic kernel. |
| Universal Launcher / **ULU** | Replaceable process, session, persistence, IPC and platform capability hosts: experimental until implementation and consumer evidence justify promotion. |
| Universal Setup / **USK** | Package, installed-state, typed-effect, transaction, recovery, refusal and audit law: the semantic kernel. |
| Universal Setup / **USU** | Replaceable source, archive, cache, filesystem, elevation, native-integration and trust capability hosts: experimental until effect and recovery evidence justify promotion. |
| FacMan | Factorio meaning, compatibility, discovery, instances, readiness, content, acquisition, launch intent, product policy, presentation, support, release selection and the resolved product graph. |

Providers define reusable capability. Products define meaning. A
deterministic product-owned compiler resolves one exact target. Native shells
project the resulting semantics. No fourth common implementation repository,
atomic cross-repository merge, floating provider identity, or universal GUI
ABI is admitted by this constitution.

ULU and USU are layers within the two provider repositories, not repositories
four and five. No host-layer roadmap authorizes a mass rewrite or relocation.
Generic code crosses a repository boundary only through characterized,
additive, independently releasable and reversibly adopted changes.

## Compatibility vector

One product version is not a universal compatibility answer. Each released
record identifies its relevant surfaces independently:

```text
product version
provider package version
C ABI version
command protocol version
contract-set identity
persisted-state version
package/recipe format version
extension API version
presentation contract version
target-profile version
update-metadata version
```

Canonical product builds bind exact source, package, ABI, contract, target,
toolchain, and runtime identities. Version ranges may support development or
downstream experimentation, but may not silently alter a qualified release.

All three repositories use one maturity vocabulary:

```text
draft
fixture-qualified
single-consumer-qualified
two-consumer-qualified
release-candidate-qualified
release-qualified
stable
deprecated
retired
```

A promotion names the contract owner and version, compatible predecessor set,
real consumers, positive and negative corpora, migration and rollback paths,
support window, evidence identities, and invalidation triggers. A package
version, ABI version, contract maturity, product capability, and support claim
remain distinct facts.

## Capability-guarantee model

A flat capability label cannot describe whether a route is safe. Resolution
uses four independent axes:

```text
availability:
  available | temporarily_unavailable | unsupported
  | policy_refused | qualification_refused

implementation:
  native | polyfill | local_sidecar | remote_gateway | delegated

guarantees:
  capability-specific exact properties and explicitly weaker alternatives

qualification and support:
  unobserved | fixture-qualified | build-qualified | runtime-qualified
  | journey-qualified | release-qualified
  plus unsupported | experimental | preview | supported | best_effort
  | maintenance | security_only | end_of_life
```

Process execution, for example, is described by executable identity, shell
interpolation, environment closure, handle inheritance, process-tree
containment, output bounds, timeout and cancellation classification, and
unknown-outcome recovery. Missing security or transaction guarantees cause
refusal unless product policy explicitly admits a named degradation.

The product compiler resolves requirements, target profile, provider
capabilities, guarantees, permitted degradations, and support policy into the
selected provider set, effective guarantees, explanation, and acceptance or
refusal. The explanation records rejected alternatives and the evidence that
qualifies each selected guarantee.

## Target profiles and truthful support

Target profiles describe CPU, object format, toolchain, language/runtime,
minimum host, filesystem/path behavior, clocks, large-file support, process
and dynamic-library guarantees, security facilities, native presentation,
package formats, and qualified host corpus.

Build host, runtime floor, claimed minimum host, evidence state, publication
state, support class, and lifecycle state are separate fields. A successful
compile or modern hosted CI run never becomes a legacy support claim.

Compatibility, primary, and modern lanes may use different binaries,
frontends, runtime closures, and provider implementations while preserving
the same product and command semantics. Optional modern APIs are selected by
feature and guarantee probes. A portable equivalent or private sidecar is a
polyfill only when it preserves the required guarantee; otherwise the route
degrades explicitly or refuses.

Legacy compatibility therefore uses exact target profiles, frozen toolchains,
capability-selected ULU/USU providers and, where bounded and independently
qualified, private sidecars. It never requires one executable or one provider
implementation to span every supported and historical host.

## Module and provider evolution

The target remains a contract-driven modular monolith with replaceable
providers. Every admitted module declares owner, public contract, private
implementation, allowed and forbidden dependencies, effect classes,
persistent records, platform ports, evidence, and deprecation state.

Product-neutral code moves to a provider only after characterization, an
accepted provider contract, a genuinely different consumer, reversible
provider implementation, reversible consumer adoption, and exact reference
census. Reserved or incomplete roots are not roadmap promises and remain
excluded from default builds and SDK exports.

Generate schema bindings, descriptors, registries, diagnostic catalogues,
contract indexes, compatibility reports, and API tables when generation is
deterministic and source-identified. Domain rules, transaction decisions,
recovery policy, user explanations, native layouts, and security-sensitive
adapters remain reviewed hand-written code.

## Extension trust ladder

Extension capability grows only through a reviewed trust ladder:

| Level | Mechanism | Default authority |
| --- | --- | --- |
| L0 | User data, preferences, profiles, themes, localisation | Unprivileged |
| L1 | Validated declarative extension package | Declared data only |
| L2 | Bounded out-of-process extension | Explicit capability-scoped protocol |
| L3 | Sandboxed modern-lane component | Explicit imported capabilities |
| L4 | Trusted native provider | Signed and separately admitted |

FacMan owns the first product-specific declarative extension contract. It may
describe discovery, launch templates, compatibility data, diagnostics,
import/export mappings, localisation, and bounded theme assets. It may not
grant setup, process, credential, network, publication, arbitrary widget, or
native-code authority.

Executable extensions remain post-v1. Universal Setup never loads untrusted
third-party code into its mutation process; an extension may propose data,
while USK independently validates, plans, authorizes, applies, and verifies
effects. A marketplace remains deferred until signing, revocation, withdrawal,
incident response, migration, and support ownership are proven.

## Configuration and resolved state

Configuration resolves in a visible order:

```text
built-in defaults
-> machine/site policy
-> user defaults
-> workspace settings
-> instance/profile settings
-> one-session overrides
```

Every effective value can explain its source, lock state, overridden values,
reason, and validation status. User specifications record desired state;
generated locks record exact installation, content, provider, capability,
contract, target, and launch resolution.

Themes remain declarative. Native accessibility, focus, window chrome,
security prompts, error meaning, high contrast, reduced motion, and safe mode
override custom appearance.

## Durable state and migration law

Every durable record carries schema identity and version, stable record ID,
revision, producer identity, canonical digest, dependency identities,
extension namespaces, and migration provenance. Portable identity is logical;
absolute host paths and filesystem identity are separate host bindings.

Security-sensitive commands remain closed and reject unknown fields. Durable
user state may preserve uninterpreted data only inside explicit namespaced
extension envelopes. Unknown data never grants authority or changes
transaction meaning.

Migration is always:

```text
read old
-> validate
-> create backup
-> transform in staging
-> validate new
-> atomically publish
-> retain rollback reference
-> record migration evidence
```

Each transition is explicit, adjacent-version where practical, idempotent,
restart-safe, bounded, independently testable, non-destructive before commit,
and reversible where promised. Readable, writable, upgradable, downgradeable,
and exportable versions are separate support statements. Derived indexes and
caches are disposable and rebuildable; specifications, provider records,
content manifests, installed state, ownership, journals, and audit chains are
authoritative.

## Explanation, Doctor, and Safe Mode

Product readiness and refusal share one explanation graph:

```text
observed fact
-> applicable rule
-> conclusion
-> blocker or warning
-> available remedy
-> remedy effects
-> semantic action
```

Native shells, CLI, TUI, diagnostics, and support export project the same
revision-bound explanation rather than inventing platform-specific meaning.

The later Doctor model separates read-only `inspect`, `explain`, and `plan`
from admitted `apply`, followed by independent `verify` and bounded `export`.
Safe Mode uses System Native presentation, disables third-party extensions,
network, account providers, automatic migration, and background tasks, and
opens workspaces read-only where possible. It retains inspection, export,
activity, Last Run, recovery, backup restore, extension disablement, and entry
to an external maintenance host.

ULK operation/session, USK transaction, FacMan content/workspace, and
maintenance/update journals remain distinct and are cross-linked by stable
operation, plan, and resource identities.

## Product milestones and release-train law

The milestone names have closed meanings:

| Milestone | Completion contract |
| --- | --- |
| **C1** | Internal alpha foundation for one exact Windows route, WinForms reference journey, package/recovery evidence and the reusable semantic spine. It is not public `0.1.0`. |
| **`0.1.0`** | First public beta: every admitted Windows 10/11 x64 capability is complete through the shared backend, CLI, TUI and WinForms, with no fixture-only or advertised-incomplete ordinary workflow. |
| **`1.0.0`** | Full supported release: all admitted CLI, TUI, WinForms, AppKit, GTK and Qt Widgets rows close, with zero required gaps and complete lifecycle, accessibility, package and support evidence. |

“Complete” is measured against a frozen finite matrix. It does not mean every
conceivable storefront, server, account system, operating-system integration,
extension or future frontend. Deferred capabilities remain explicit and
unadvertised; required capabilities may not hide behind Advanced or an
undocumented command.

Autonomous work may plan, implement, refactor, document, test and qualify alpha
candidates. Human testing and accountable promotion occur at the end of each
meaningful beta, release-candidate and stable train, after the automated matrix
is satisfied. This avoids human-in-the-loop construction without postponing
all experiential evidence until after the entire multi-platform programme.

The ratified planning records are:

- [`version_train.v1.toml`](../../release/index/version_train.v1.toml)
- [`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml)
- [`plan.v1.toml`](../../release/index/plan.v1.toml)
- [`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml)
- [append-only release ledger](../../release/ledger/README.md)

Their activation gates remain controlling. Referencing them here does not
create a candidate, move a canonical ref, allocate a release number, issue a
tag, authorize human evidence, sign, publish, support or withdraw anything.

## Deterministic intelligence and release trust

Automatic understanding remains read-only and deterministic. Optional
advisors consume bounded snapshots and may return typed recommendations with
facts, evidence, freshness, assumptions, proposed semantic action, predicted
effects, and alternatives. They receive no permit, credential, ambient
filesystem/network access, setup authority, process authority, or release
authority.

Released contract corpora retain public headers, ABI manifests, symbols,
schemas, good and bad state fixtures, requests/results, packages, migrations,
support matrices, toolchains, and provider identities. Release capsules bind
source, locks, build instructions, packages, debug symbols, SBOM, provenance,
attestations, signatures, update metadata, compatibility corpus, recovery
tools, and lifecycle statements. Exact trust mechanisms and specification
versions are selected and reviewed in their later WorkUnits, not asserted by
this planning constitution.

## Prepared post-C1 WorkUnits

The canonical later horizon contains:

```text
UNIVERSAL-COMPATIBILITY-EVOLUTION-CONSTITUTION-01
UNIVERSAL-CAPABILITY-GUARANTEE-MODEL-01
UNIVERSAL-DURABLE-STATE-MIGRATION-LAW-01
FACMAN-PRESENTATION-EXPLANATION-GRAPH-01
FACMAN-DOCTOR-AND-SAFE-MODE-01
```

They produce small contracts, corpora, and validators after C1. They do not
open a provider repin, source-closure acceptance, Setup mutation, Factorio or
product execution, credential/network use, extension execution, signing,
publication, route capability, or support claim.
