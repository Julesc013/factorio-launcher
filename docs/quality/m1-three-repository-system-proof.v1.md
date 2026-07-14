# M1 Three-Repository System Proof

## Result

`m1_three_repository_system_proof` is the fixture-only authority proof for the
Managed Portable Install Foundation. It composes the real libraries from
Universal Setup, Universal Launcher, and FacMan in one native CTest journey.

The proof creates only an exclusively owned disposable root under the native
temporary directory. Its synthetic ZIP contains no proprietary binaries and
is removed with the rest of the fixture after every run.

## Journey

The test proves this ordered path:

1. FacMan binds its Factorio recipe to a locally generated ZIP and asks
   Universal Setup to inspect the archive without mutation.
2. Universal Setup creates and revalidates an exact digest-bound plan, stages
   the synthetic payload, commits it without clobbering, writes ownership and
   installed-state records, and verifies the committed closure.
3. Universal Launcher validates the reviewed plan identity and projects the
   completed result into a managed install reference.
4. FacMan persists the exact setup-state, verification, and state-revision
   identities, creates an instance, and renders a launch preview only.
5. Universal Setup verifies, moves, and repairs the managed closure. Launcher
   refreshes the reference only after the new root verifies; the old root retained
   result remains explicit and the previous launch identity becomes stale.
6. Uninstall first retains and reports an unknown operator file. A later clean
   plan removes only the remaining recorded owned state and Launcher archives
   the reference.
7. A separately interrupted visible-target transaction is surfaced as
   `recovery_required`, inspected, resumed, verified, and completed.

## Authority boundary

This proof does not make fixture authority available to ordinary users.
Every FacMan setup apply command still returns `setup_apply_not_authorized`.
The test directly composes Setup's internal lifecycle library only inside its
disposable root, and it calls FacMan's refusal path to prove that `run.execute`
remains unavailable with `isolation_not_proven`.

The human-reviewed H1 Fail remains authoritative. This proof makes no claim
about a licensed standalone archive, publisher authenticity, real Factorio
execution, signing, publication, network access, Steam mutation, registry,
elevation, package-manager, or system-wide installation behavior.
