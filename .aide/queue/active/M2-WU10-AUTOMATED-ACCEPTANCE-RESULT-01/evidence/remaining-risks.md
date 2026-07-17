# Remaining Risks

- The accepted verifier revision cannot produce `EvidencePass` from native
  Universal Setup journals because it imposes an unsupported sorted-key byte
  requirement.
- The verifier and its generated fixture require an independently merged
  policy-only correction before any later run can be accepted.
- The failed run remains diagnostic evidence only and must not be reused as the
  sole passing result after that correction.
- `MachinePass`, WU10 closeout, ordinary setup candidacy, and every broader
  authority remain unavailable.
