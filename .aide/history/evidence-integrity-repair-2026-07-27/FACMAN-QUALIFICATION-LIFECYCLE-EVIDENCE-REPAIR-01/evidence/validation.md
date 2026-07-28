# Validation

Status: PASS.

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

PR 84 at exact head `ac56d30b90f8815054108d20291b17af2f34a34b`
passed the application-kit, C/C++, C#, Linux coverage, macOS archive, policy,
Python and CodeQL jobs. The duplicated Linux-native, macOS-native-CLI and
Windows-native-package jobs failed only in the same three generated-state
assertions.

The hosted-only mismatch was traced to an empty untracked local directory at
`.aide/queue/next/FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-02`.
Local state generation enumerated that directory as an unknown duplicate
queue record, while a clean hosted checkout could not contain an untracked
empty directory. The empty directory contained no files and was removed; the
canonical machine and compact current-state surfaces were then regenerated.

The exact promotion obligation profile passed after the correction:

- 528 Python tests passed;
- 9 skips were classified optional or platform-unsupported;
- required blocked, unknown, failure and error counts were zero;
- native, package, provenance, release, policy, security, AIDE, strict,
  project-state and cross-repository obligations passed;
- both frozen policy digests remained exact.

PR 84 passed every required hosted check at corrected exact head
`0a2eaa3867496185782234b1d76cf73aa0ab51af`: both Linux-native,
macOS-native-CLI and Windows-native-package jobs, both application-kit,
C/C++, C#, Linux-coverage, macOS-archive, Python and policy jobs, and CodeQL.
The reviewed change merged to `dev` as
`d1a3c2029a4ae21c58eda34d7011938bf7bf04cb`.

The repair is verified. Candidate qualification remains a separate fresh
remote-only proof and no product or execution authority is inferred.
