# Changed files

Source commit `1b962531f1d386294b44c2230c230c9f66ad2fcc` changes exactly:

- `runtime/client/facman_transport_process.cpp`: applies the 1 MiB stdout bound and preserves typed uncertainty, recovery, error text, and progress ordering when a child response cannot be trusted.
- `tests/native/facman_client_smoke.cpp`: validates success, refusal, timeout, cancellation, empty/malformed/oversized responses, outer and semantic identity mismatches, recovery, cleanup, messages, and progress.
- `tests/native/facman_process_probe.cpp`: supplies the bounded fault and identity fixtures used by the native smoke.

The task branch starts at `dev@275d24bee63d661cc2e8c7a939d720ca95d0fd01`. Merge commit `1c4f63f9430fb679f881760fd91e766f301a12af` adds current `main@dc81e5eb1bdfec4b0ed8c8640c04b2d4235f6e36` as ancestry without changing the task source tree. This evidence and `status.yaml` record the source-validation state; protected integration remains pending.
