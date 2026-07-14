<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU1 Live Target Policy

Status: provider-integrated policy proof; no live mutation authority.

This checkpoint records the first M2 vertical slice: Universal Setup can make
a deterministic, fail-closed policy decision from already-inspected target
evidence. It does not inspect the host, activate public lifecycle commands, or
perform filesystem mutation.

## Bound identities

| Repository/evidence | Identity |
| --- | --- |
| Universal Setup task | `804ae1ea2f9fdb78525a0a3ef09069b51d8bb1c1` |
| Universal Setup canonical `main` | `f322655fa8fa287a400f7afb6c661eade30d707b` |
| Universal Setup push / PR / main CI | `29316580182` / `29316591892` / `29316660078` |
| Universal Launcher retained provider | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` |
| FacMan clean package-proof source | `dfa0d8ad3c4cf5634896a67f9908ef8a5a922983` |

The Universal Setup proof passed 11 native tests, 19 Python tests, sanitizers,
and bounded fuzzing. The integrated FacMan proof passed 36 native tests, 20
focused Python cases, complete strict validation, and 14/14 required Windows
package tests.

## Policy law

The complete target taxonomy is:

```text
fixture
disposable_test
operator_acceptance
managed_portable
imported
foreign_owned
steam_managed
per_user
system_wide
```

Only `operator_acceptance` can be accepted before the human gate, and only
strictly below `D:\FacMan-Live-Acceptance\M2`. `managed_portable` requires the
later `accepted_live_portable` activation that a human M2 Pass may authorize.
All other classes refuse.

An accepted decision binds the explicit absolute target, nonexistent/empty
state, local filesystem identity, stable link/reparse-free components, absent
mount redirection, protected-root exclusion, capacity, source/target
separation, and every persistent effect. The evaluator is pure and grants no
mutation by itself.

## Reproducible package proof

| Evidence | Identity |
| --- | --- |
| archive | 1,915,237 bytes; `2410caa6a626f16305b64a79652d9b29ef5adebb17bd4a74ec4c188e40899446` |
| package tree | 384 files; `58be84a38006324da84b129239a5aefe2608ac2074a8e37cb91a119e0988f4d1` |
| SBOM | `7e78664f5965ba933b5b7aa3096fde8738c492b0dcfbbeb60f68795e0d911ba3` |
| provenance | `8d3bf8692a00c9a2b20b0cd3034d2ee77697e229dc22c16e3d7665d2d89de80e` |

The package report records clean sources, byte identity across independent
roots, unsigned/unpublished authenticity, unchanged execution authority, and
no H1 inference.

## Authority retained

- Public inspect/plan/apply lifecycle activation remains WU2 work.
- Ordinary live-target apply remains unavailable pending operator acceptance.
- The operator verdict remains `pending`; automation did not create it.
- No existing Factorio installation, Steam state, registry, shortcut, network,
  credential, elevation, package-manager, installer, or product process was
  touched.
- Execution, H1, Safe beta, signing, and publication remain unavailable.
