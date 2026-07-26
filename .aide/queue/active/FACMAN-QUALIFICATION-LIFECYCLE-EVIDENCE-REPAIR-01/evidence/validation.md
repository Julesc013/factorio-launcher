# Validation

Status: LOCAL PASS; HOSTED REVIEW PENDING.

The first live remote-only qualification passed source closure and product
authentication, then failed closed before qualification output with:

```text
staged Instance did not produce the exact non-executing candidate projection
```

Exact diagnostic preflight identified
`launcher_install_not_active`: the staged install record contained an empty
lifecycle, empty verification identity, empty state revision, and
`verification.status = structural`.

No permit was issued, no Factorio process was started, no observer capture or
human verdict occurred, and no authority was promoted.

The repaired implementation derives the verification identity from the
current no-follow stable file identity, exact executable size and SHA-256,
exact Factorio version, exact Wube signer, executable path and install id.
The state revision is the canonical digest of the complete staged
installation record. A mismatch is refused before the workspace is created.

Observed validation:

- focused producer/coordinator suite: 9 of 9 passed;
- live non-executing diagnostic against the remote-only FacMan
  `426d13cc2f68782b40eae66f0fb0621a607b7998` candidate: PASS;
- live diagnostic qualification binding:
  `fe5945fc55d0b85d49d1e2e1486a3c8334e12b40a53d609539b980128815cb80`;
- complete Python suite under the repository owner: 528 passed with 9
  expected optional/platform skips;
- strict validation: PASS with 300 schemas;
- project-state validation: PASS;
- portable AIDE Lite validation: PASS;
- exact existing remote-only native graph: 55 of 55 CTests passed;
- hermetic policy digest remained
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- instance-isolated policy digest remained
  `8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432`.

The first full Python attempt ran inside the offline sandbox, which cannot
inspect sibling repository `.git` directories; it failed dependency/package
preflight by reporting both Universal repositories as non-repositories.
The same complete suite was rerun under the repository owner with only
command-scoped safe-directory entries and passed. No check was skipped or
weakened.

The implementation was committed as
`f9b80e080569b7c67d09ef199912d4ce5945eca6`. From that clean checkout, the
required Windows package proof regenerated the exact source identity and
passed all 14 required obligations with zero skips.

Hosted validation remains a separate merge prerequisite.
