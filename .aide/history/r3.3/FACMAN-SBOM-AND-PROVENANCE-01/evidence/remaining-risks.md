# Remaining Risks

- An unsigned provenance record can make build inputs inspectable but cannot
  authenticate the publisher or prevent a malicious party from replacing both
  an artifact and its adjacent record.
- CI identity is evidence supplied by the build environment, not a signed
  attestation or transparency-log entry.
- Release publication, signatures, setup mutation, and authenticity remain
  separate authority gates.
