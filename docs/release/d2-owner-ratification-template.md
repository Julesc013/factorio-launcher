# D2 owner-ratification template

This template is deliberately inert until completed and committed by the owner.
Its presence is not ratification.

```text
record_id:
owner_identity:
ratified_at:
policy_revision:
policy_tree:
implementation_schema_sha256:
assurance_schema_sha256:
policy_admission_schema_sha256:
integrator_identity:
integrator_is_independent: true|false
protected_dev_merge_authorized: true|false
effective_from:
expires_at:
revocation_record:
d4_authority_granted: false
owner_signature_or_approved_repository_check:
```

Ratification is valid only when all exact fields are present, the named policy
revision is canonical, the integrator identity is independent of implementation
and assurance, and the repository policy validator accepts the record. It does
not grant self-approval, self-merge, force-push, branch-protection bypass,
tagging, credentials, signing, publication, route promotion, stable promotion,
or human-verdict authority.
