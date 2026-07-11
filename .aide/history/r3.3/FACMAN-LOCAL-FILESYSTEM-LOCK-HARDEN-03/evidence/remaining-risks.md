# Remaining Risks

- Local stable-handle proof cannot establish SMB, NFS, cloud-sync, cluster, or
  other multi-host lock semantics.
- Filesystem classification APIs and mounted-filesystem behavior vary; unknown
  or unsupported identities must refuse rather than guess.
- `run.execute` and real Factorio isolation remain separately human-gated.
