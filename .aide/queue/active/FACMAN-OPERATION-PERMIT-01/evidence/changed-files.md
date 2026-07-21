# OperationPermit changed-file evidence

The WorkUnit is active. Its reviewed implementation scope now includes the
dormant Factorio launch verifier under `runtime/factorio/launch/**` so Gate 3
can prove independent owning-provider validation and atomic consumption. The
verifier is not an execution path and cannot launch Factorio.

The scope also includes generated `.aide/memory/**` and root `README.md` truth
surfaces because contract and refusal counts must remain generator-consistent
during the active gate.

The contract-law slice adds seven internal `common.*permit*.v1` schemas, the
closed 25-code permit refusal family, and the versioned architecture law. It
also regenerates the development-state counts to 268 schemas and 242 refusal
codes. No command, route, frontend, runtime authenticator, provider effect, or
product issuance surface is introduced by this slice.
