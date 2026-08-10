# Remaining risks

- A task-ref source-closure report does not yet exist.
- The current developer workstation is not a fresh or snapshot-restored host
  and therefore does not satisfy the qualified-host contract.
- GitHub currently exposes zero self-hosted runners and no repository secret or
  variable binding for a Factorio archive.
- Hyper-V and Windows Sandbox are installed locally, but no clean VM is
  provisioned with the exact native toolchain and evidence custody.
- No private read-only Factorio 2.0.77 Windows x64 standalone archive was found
  in the bounded Factorio project and `E:\Downloads` custody checks.
- A qualified host and archive must be supplied before the one task-ref run;
  the developer workstation must not be substituted for that proof host.
- Merging this admission branch remains a separate owner decision even after task-ref evidence passes.
- Canonical-dev closure requires a second fresh empty-root run after admission integration.
- The three admission fields must be revoked immediately after canonical closure before qualification activates.
