# WinForms C1 transport hardening 01

`FACMAN-WINFORMS-C1-TRANSPORT-HARDENING-01` is accepted and merged by pull
request `#119` as `7ebbfa37b23ee173cbb15f399935d0e035e79375`.
Its exact parents are canonical base
`bfac7ce41f19856522b5f9603320f444b8f45094` and exact task head
`a90720ca994352f8a327399be718ab2feca91256`; the task head is contained by the
merge.

The bounded WorkUnit has made the existing WinForms process RPC fail closed for
malformed, mismatched, oversized, timed-out, interrupted, and post-dispatch
unknown backend outcomes. It adds executable Windows behavior proof and
complete descendant containment without changing backend-resolution policy.

The client now enforces strict raw-byte budgets, strict UTF-8 and closed JSON,
exact response/request/command/operation/attempt correlation, and an explicit
pre-dispatch versus possible-dispatch state law. Once dispatch becomes
possible, uncertainty is always `outcome_unknown`, effects may have occurred,
and recovery inspection is required. A Windows Job Object contains the full
backend tree before the primary thread resumes.

Local qualification is complete: the executable transport harness passes 38
cases, canonical MSVC Debug and Release matrices each pass 58/58 tests, the
promotion Python suite passes 668 tests with zero required or unknown skips,
and the unsigned WinForms package reconstruction/runtime smoke verifies 398
files. Exact clean-head packaging and hosted task-head qualification are
out-of-tree review evidence produced after the final tracked closeout commit.

The merged-dev closeout found no remaining local task branch or worktree to
remove. The published remote task ref is retained because this local closeout
performs no authenticated network write.

Universal Launcher and Universal Setup pins remain unchanged. Revalidation-04
remains superseded immutable history. This WorkUnit creates no successor stage
and grants no observer, prepare, permit, Factorio execution, verdict, route,
Setup mutation, credential, network, signing, or publication authority.
