# Ecosystem Vision

The launcher ecosystem is three sibling repositories, not one product
repository with some reusable code and not a fourth common implementation
repository:

```text
factorio-launcher   FacMan, the Factorio product
universal-launcher ULK/ULU, the runnable-product platform
universal-setup    USK/USU, the installed-software platform
```

Factorio proves the universal launcher and setup contracts through FacMan.
Dominium and later genuinely different products prove that those contracts are
universal. FacMan ships as the first serious Factorio product binding.

## Kernel, host, and product law

The provider repositories separate durable meaning from replaceable platform
mechanism:

```text
ULK — Universal Launcher Kernel
  runnable-product references, plans, operations, outcomes and handoff law

ULU — Universal Launcher Host
  experimental process, session, persistence, IPC and platform providers

USK — Universal Setup Kernel
  package, installed-state, transaction, recovery and audit law

USU — Universal Setup Host
  experimental source, archive, cache, filesystem, elevation and trust providers
```

ULK and USK are the semantic kernels. ULU and USU are capability-host and
provider layers, not new repositories and not miscellaneous public APIs. Their
host surfaces remain experimental until callable implementations, provider
conformance, migrations, and real consumers justify promotion.

FacMan owns the resolved product graph and every Factorio-specific decision:

```text
Factorio meaning and compatibility
product policy and readiness
instances, profiles, content, saves and launch intent
acquisition and entitlement decisions
native presentation and player journeys
release composition, support and exact provider selection
```

A deterministic FacMan-owned compiler resolves product definition, target
profile, exact provider locks, support policy, package rules and evidence into
one graph. Frontends and package producers consume that graph; they do not
reinterpret it.

Permanent rule:

```text
Universal Setup mutates installed-software state.
Universal Launcher orchestrates runnable-product state.
FacMan interprets Factorio-specific facts and owns product meaning.
Frontends project semantic actions and reports.
Contracts preserve compatibility.
Validators prevent regression.
```

No convergence milestone authorizes a repository merger, `universal-common`,
mass code relocation, language rewrite, or one executable spanning every host.
Reusable code moves only after characterization, an additive provider contract,
independent provider proof, a real second consumer, reversible adoption and a
normal deletion or thinning of the product incubator.

## Product completion train

C1 is the internal alpha foundation: one exact Windows route, bounded native
shell, package and recovery evidence. It is not the public `0.1.0` contract.

Public `0.1.0` is the complete finite Windows 10/11 x64 product admitted by its
frozen capability matrix. Every required capability must be implemented end to
end through the shared backend, CLI, TUI and WinForms, with positive, refusal,
recovery, package, accessibility and documentation evidence. Features outside
that frozen matrix are explicitly deferred rather than half advertised.

`1.0.0` is a measurable supported-release contract. All admitted rows must be
complete through CLI, TUI, WinForms, AppKit, GTK and Qt on their exact supported
target profiles, with zero required gaps and no advertised incomplete feature.
WinUI, SwiftUI, remote administration and other later projections are not
implicitly part of that contract.

Legacy compatibility uses independently qualified target profiles, binaries,
runtime closures, providers and bounded sidecars. It never requires one modern
binary to run unchanged on every historical operating system.

The ratified planning contracts are:

- [`version_train.v1.toml`](../../release/index/version_train.v1.toml)
- [`autonomy_policy.v1.toml`](../../release/index/autonomy_policy.v1.toml)
- [`milestones.v1.toml`](../../release/index/milestones.v1.toml)
- [`capability_frontend_matrix.v1.toml`](../../release/index/capability_frontend_matrix.v1.toml)
- [`withdrawal_policy.v1.toml`](../../release/index/withdrawal_policy.v1.toml)

They define activation and promotion gates. Mentioning them here grants no tag,
merge, human verdict, signing, publication, support or withdrawal authority.
Autonomous work may construct and qualify alpha candidates; accountable human
validation occurs at the end of each beta, release-candidate and stable train,
not inside every implementation step and not once after the entire programme.

FacMan should make the universal launcher concrete through real Factorio
instances, profiles, artifact sets, launch plans, diagnostics, and dry-run
execution. It should not absorb setup mutation or turn Factorio-specific rules
into universal launcher concepts.
