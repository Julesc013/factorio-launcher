# FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01

Date: 2026-08-10

State: `superseded_not_run_deferred_external`

> Historical admission design only. Reconciliation on 12 August 2026 closed
> all three temporary gates. No task-ref or canonical-dev evidence run
> occurred, and the current valid evidence set is empty.

## Exact base

PR #123 integrated the reviewed source-closure implementation as the normal
two-parent `dev` merge:

```text
merge   4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f
parent1 7c184752cae8cfd747a242a33ef47f77f6a56394
parent2 ef318ad986a927809cbd4af8d39f1a84f05a1e93
tree    5e127a96825170c04b71736f6598aeb4a98ba0ef
```

General CI, schema validation, security policy, CodeQL, and the synthetic
product TCK all passed at that exact merge. The admission branch begins from
that exact commit and tree.

## Historical proposed transition

The admission candidate opened exactly:

```text
new_evidence_execution_authorized      true
source_closure_execution_authorized    true
v2.new_source_closure_evidence_allowed true
```

The index digest binds the complete transition. Route v1 remains historical;
route v2 remains the sole current evidence target. Qualification, capability,
promotion, Factorio execution, observer capture, stage creation, baseline,
prepare, permits, Setup mutation, credentials, signing, publication, support,
and human verdict authority remain false.

## Immutable inputs

The admission validator pins these exact SHA-256 identities:

```text
route v1                         98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
route v2                         765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8
workspace lock                   510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3
provider lock                    59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249
remote source-closure engine     e48e1837ad897c7fff3a534deb9e98b5b5a045364b3c80a2a07e54fd56512506
workspace proof engine           cd48080eef50d4b60d31efbdf2f23d83e8ed0cf6b2043a4155545f80330b3a59
source-closure report schema     5729afb042055405af4cebba6817090e2e0901227b2f614f973d5edc69cfbfc0
```

Changing any of these inputs is outside this WorkUnit and fails validation.

## Run budget and evidence law

The admitted task ref is:

```text
refs/heads/task/facman-successor-play-source-closure-admission-01
```

One qualified clean-Windows task-ref run is permitted. It must bind the exact
remote task head, route v2, `.02` evidence identity, canonical provider commits
and trees, toolchain, read-only Factorio archive and executable member, package,
manifest, release-resolution root, SBOM/provenance, test counts, classified
skips, clean source state, and a complete false product-authority table.

The task-ref report remains rehearsal evidence. Merging this branch is a
separate owner decision. Only after an accepted merge may one fresh canonical
`dev` run occur. A successful canonical run must be followed by a reviewed
revocation/closeout that closes the three gates before candidate qualification
can activate.

## Qualified host

The host must be a fresh or snapshot-restored Windows x64 VM or private runner
with the complete Visual Studio native toolchain, no user FacMan workspace, no
user Factorio installation, no production credentials or signing keys, empty
short clone/build roots, canonical credential-free HTTPS remotes, a private
read-only Factorio 2.0.77 standalone archive, and an out-of-tree exclusive
evidence destination.

Source closure may inspect the archive and construct FacMan packages. It may
not execute or install Factorio, materialize an instance, invoke Setup mutation,
capture an observer, prepare, issue a permit, sign, or publish.

The 2026-08-10 local host audit found no GitHub self-hosted runner, no repository
archive binding, no provisioned local Hyper-V VM, and no archive in the bounded
Factorio project or `E:\Downloads` locations. Windows Sandbox is installed, but
it is not a prequalified, toolchain-ready proof host. The task-ref proof remains
blocked on a qualified clean host and private read-only archive; it was not
simulated on the developer workstation.

Local validation passed the 337-schema check, AIDE Lite, generated truth and
route/admission checks, a 153-test consolidated Python suite, two exact-provider
MSVC builds, and 38 of 38 native tests. These checks validate the admission
candidate; they do not substitute for the single-run source-closure report.

## Deferred matrix corrections

This admission does not modify the capability matrix. The later
`FACMAN-CAPABILITY-FRONTEND-MATRIX-01` WorkUnit must keep one row per semantic
capability, generate a separate many-to-many command-to-capability census, and
reject unmapped ordinary commands. It must also reclassify
`content.local_modsets` from `setup_mutation` to
`instance_content_mutation`, preserving FacMan ownership of instance content
and USK ownership of installed-software mutation.
