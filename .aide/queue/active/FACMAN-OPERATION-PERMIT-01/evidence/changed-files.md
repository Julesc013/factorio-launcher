# OperationPermit changed-file evidence

The WorkUnit is active. Its reviewed implementation scope now includes the
dormant Factorio launch verifier under `runtime/factorio/launch/**` so Gate 3
can prove independent owning-provider validation and atomic consumption. The
verifier is not an execution path and cannot launch Factorio.

The scope also includes generated `.aide/memory/**` and root `README.md` truth
surfaces because contract and refusal counts must remain generator-consistent
during the active gate.

No permit runtime, contract, route, provider, or frontend implementation
change has been accepted yet. This file will be updated as bounded
implementation slices are committed.
