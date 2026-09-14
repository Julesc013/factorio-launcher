# Changed files

The already integrated source commit `1b962531f1d386294b44c2230c230c9f66ad2fcc` changes exactly:

- `runtime/client/facman_transport_process.cpp`: applies the 1 MiB stdout bound and preserves typed uncertainty, recovery, error text, and progress ordering when a child response cannot be trusted.
- `tests/native/facman_client_smoke.cpp`: validates success, refusal, timeout, cancellation, empty/malformed/oversized responses, outer and semantic identity mismatches, recovery, cleanup, messages, and progress.
- `tests/native/facman_process_probe.cpp`: supplies the bounded fault and identity fixtures used by the native smoke.

This checkpoint starts at exact protected `dev@a158a6aa6eae947832fdd16101531ac122f7a3a6`, tree `f47600447ae36b67e35d077fa05e94817f506a8d`. It:

- moves the terminal WorkUnit from `next` to `active` and updates the canonical and generated plan views;
- corrects `docs/architecture/unified_interaction_platform.v1.md` so nonempty `NO_COLOR` disables color without forcing an otherwise capable terminal into linear mode;
- records current Windows native, RPC, terminal, TUI, ConPTY, architecture and AIDE validation without rewriting the immutable source-review receipt.

PR 279 normally integrated that checkpoint into protected `dev` at
`3267db2e12f8ea4f95dd77a97736dd2afa1efc4f`. This follow-up records the exact
merge and closes the WorkUnit in canonical, queue and generated project truth.
