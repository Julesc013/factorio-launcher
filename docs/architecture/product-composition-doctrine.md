# Product Composition Doctrine

FacMan uses one permanent ownership rule:

> Providers define reusable capability. Products define meaning. A
> deterministic product-owned composition compiler resolves one exact target
> graph. Package adapters project, but never redefine, that graph. Installation
> backends preserve their own mutation authority.

This doctrine keeps three repositories independent:

```text
Universal Launcher
    reusable runnable-state infrastructure

Universal Setup
    reusable installed-state and mutation infrastructure

FacMan
    Factorio product meaning, presentation, composition, and release authority
```

## Ownership

Universal Launcher owns product-neutral references, launch capabilities,
plans, operations, sessions, process containment, and runnable state. It does
not own Factorio rules, product UI, acquisition policy, or installed-software
mutation.

Universal Setup owns product-neutral package identity, verification, topology,
lifecycle planning, transactions, installed state, repair, migration,
rollback, uninstall, recovery, and audit. It does not select FacMan release
channels, define launch intent, acquire credentials, or reinterpret product
meaning.

FacMan owns Factorio compatibility, instances, profiles, managed content,
acquisition decisions, product presentation, product settings, release
composition, target profiles, package projections, claims, and release
custody. Provider code linked into a FacMan artifact does not transfer the
provider's authority to a frontend or package script.

## Six Planes

| Plane | Owner | Release-compiler treatment |
| --- | --- | --- |
| Product meaning | FacMan | Authored product, component, claim, and compatibility inputs |
| Runnable state | Universal Launcher | Exact provider contract binding and capability closure |
| Installed state | Universal Setup | Exact provider binding plus path and lifecycle ownership |
| Acquisition | FacMan or a FacMan-owned connector | Explicitly outside resolution; a URL grants no setup authority |
| Presentation | FacMan | Entrypoints and product capability requirements |
| Release and trust | Each repository for itself | Exact identities, maturity, trust roles, and ungranted authorities |

The acquisition boundary is strict: download completion is not trust, a URL is
not package identity, and acquisition never authorizes setup. Universal Setup
begins only with a stable local candidate and expected evidence, then reopens
and verifies that candidate independently.

## Authoritative Graphs

The Universal Launcher graph describes what can run. The Universal Setup graph
describes what is installed and who may mutate it. The FacMan resolved release
graph binds those provider graphs to one product version, one target, one
toolchain, one component closure, one staged-path law, one artifact plan, and
one set of evidence obligations.

These graphs are related but not interchangeable. A capability may be present
without being enabled; enabled code may still lack operation authority; and an
authorized operation does not establish a support claim.

## Identity Layers

The compiler keeps reviewed source base, observed build source, provider source
pin, provider package/ABI/contract identity, resolved product digest, staged
image, package digest, signature, publisher identity, and support claim as
separate facts.

`release/index/version.v2.toml` currently records the reviewed source base from
which the compiler work began. It must not be presented as the final source of
an artifact built from later commits. Because tracked source cannot contain the
hash of the commit that contains itself, the actual immutable build source and
tree belong in post-checkout build evidence or an externally supplied reviewed
release input. `FACMAN-RELEASE-IDENTITY-NORMALIZATION-01` is the prepared
follow-up for making that distinction machine-enforced before release use.

Packages, runtime handshakes, support bundles and evidence packets should
eventually bind one composite contract-set identity over provider package,
ABI, schema and contract sets; the product binding ABI; workspace and
installed-state schemas; command, refusal and presentation contracts; provider
revisions; and actual product revision. The composite identity still does not
grant authority or authenticate a publisher.

## Compatibility Transitions

Compatibility is modeled as a directed transition graph across FacMan version,
workspace schema, product-binding ABI, provider packages and contracts,
installed-state schema, target, package backend and Factorio compatibility.
Every transition declares preconditions, migration, backup, rollback,
downgrade, irreversibility, maintenance-host floor, evidence and support
window. Restoring only binaries while leaving state unreadable is not rollback.

## Permanent Laws

- A package format cannot define or change the product.
- Every provider change precedes consumer adoption and stays independently
  reversible.
- Contract implementation, qualification, authority, publication, and support
  remain separate states.
- Stable provider claims require two meaningfully different consumers and
  migration evidence.
- No setting, GUI action, package script, or plugin can manufacture authority.
- Native package managers retain mutation ownership of their installed files.
- FacMan never treats restoring binaries while leaving an unreadable workspace
  as rollback.
- Product frontends do not hold setup, process, credential, signing, or release
  authority.

## Ratified Scope and Deferrals

The implemented compiler covers deterministic authored truth, exact target
resolution, component and entrypoint closure, path ownership, artifact
authority, compatibility transitions, qualification plans, support claims,
canonical staging, and constrained package inspection.

It deliberately does not create a daemon, marketplace, plugin framework,
cloud sync service, automatic updater, signing service, package repository, or
new common implementation repository. Provider SDK adoption, independent
consumer proof, signing, publication, native package-manager backends, and
stable support remain separate evidence-gated work.

See [Composition Compiler](../release/COMPOSITION_COMPILER.md) for the concrete
contracts and operator workflow. See
[Universal product runtime and delivery programme](universal_multi_consumer_productization.md)
for provider productization, consumer profiles, convergence, trust and the
dependency-ordered preparation register.
