# Remaining risks

- Protected exact-head CI and integration into `dev` are pending. The WorkUnit remains active until the merged identity and current checks are recorded.
- The source validation used an owned Windows Debug build. Linux and macOS behavior depends on protected CI; no physical Linux-host qualification is claimed here.
- A pre-existing access denial in an unrelated stale task root prevents a complete workspace-hygiene measurement. No cleanup or ceiling increase was attempted.
- This slice does not execute Factorio, sign packages, create a release, publish artifacts, or provide human UX acceptance.
