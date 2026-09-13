# Remaining risks

- Protected exact-head checks and integration of this documentation/lifecycle checkpoint into `dev` are pending; the WorkUnit remains active until that identity is recorded.
- The current local execution is Windows Debug and ConPTY evidence. POSIX PTY behavior depends on protected Linux/macOS checks; no physical Linux host is claimed by this receipt.
- The CLI host's 16 MiB response ceiling is implemented, while this slice directly exercises the 1 MiB request ceiling and the process client's 1 MiB child-output refusal. A synthetic 16 MiB product response was not manufactured solely to mirror the constant.
- This slice does not execute Factorio, sign packages, publish a release, or provide human UX acceptance. Those acceptance cells remain with their owning WorkUnits.
