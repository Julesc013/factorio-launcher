# Remaining risks

- Backend executable identity remains intentionally deferred to
  `FACMAN-C1-BACKEND-IDENTITY-01`.
- Workspace-root ownership remains intentionally deferred to
  `FACMAN-WORKSPACE-ROOT-AUTHORITY-01`.
- Exact clean-head package reproducibility and hosted task-head checks are
  pending until the final tracked commit is published; they are out-of-tree
  review evidence and cannot grant product authority.
- This machine's persistent System32 `cmd.exe` RunAsAdmin compatibility flag
  requires a process-local RunAsInvoker setting for canonical MSVC builds.
- No successor Play route or product authority exists.
