# Validation — producer and diagnostic qualification

## Completed

```text
qualification/route/truth affected Python suite       PASS (108)
qualification-04 exact-root refusal                   PASS
qualification-04/revalidation-03 v3 identity          PASS
project-state generation and validation               PASS
canonical plan generation and validation              PASS
schema validation                                     PASS (304)
source-format check                                    PASS
strict validation                                      PASS
portable AIDE validation                               PASS
git diff check                                         PASS
```

The strict run used the exact clean retained provider clones at:

```text
Universal Launcher
C:\Users\Jules\AppData\Local\Temp\facman-q03-final5-clones\universal-launcher
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
C:\Users\Jules\AppData\Local\Temp\facman-q03-final5-clones\universal-setup
3048128963dc718a7c38c1cfcdda9e813a23b0db
```

Transient validation output was isolated under the WorkUnit-specific external
temporary root. An initial strict invocation without provider discovery
stopped at the workspace-lock check. A second invocation correctly rejected
an in-repository temporary package-skeleton output root. Neither is counted as
acceptance; the corrected exact-provider, external-TEMP run passed.

No qualification report, observer self-test, WPR session, `prepare`, permit,
or Factorio execution is part of this source phase.

## Accepted remote producer integration

```text
task revision                    c8bc937f1190d1068745a255b9d28ff24a499c0c
PR                              #99
dev integration                 569883a86c50ca203ccbecec6d37216f22f7c6a0

PR CI                           PASS 30575090336
PR schema-check                 PASS 30575090335
PR code-security                PASS 30575090328
PR security-policy              PASS 30575090250

integrated-dev CI               PASS 30576115373
integrated-dev schema-check     PASS 30576115655
integrated-dev code-security    PASS 30576115573
integrated-dev security-policy  PASS 30576116097
```

## Diagnostic remote source closure

The first empty-root attempt stopped because the Windows checkout omitted a
tracked long path. It produced no report and remains diagnostic. The second
attempt used an explicit per-process `core.longpaths=true` binding and passed:

```text
FacMan                           569883a86c50ca203ccbecec6d37216f22f7c6a0
Universal Launcher              7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup                 3048128963dc718a7c38c1cfcdda9e813a23b0db
closure report SHA-256          300ed1c9dac88d8d69085b79ed23e394cd9f9ed24096a5d727b1cf3bcb78b54c
package artifact SHA-256        c9015800c2ab569810bdf4cc15628f8df19ca4d922d1043113ab4a2d41082baf
provenance SHA-256              c5c8b8d8d0b07fdd2a130af9a322c2fac1678ed7bcfacf23b6877f39416b33
FacMan native tests             PASS 58
FacMan Python tests             PASS 569
Launcher native tests           PASS 5
Setup native tests              PASS 16
Windows package tests           PASS 14/14
```

## Diagnostic qualification-04

```text
qualification digest            b6d1e7b030a17cf5279d363c341a8405526363217c96928d78d199d6a073363b
report digest                   8116af7b8d9df1089e6211aca42273e44279f62eb1f77af0397301194373cb9d
binding file SHA-256            3f2de719929065d4442546e66fb1729dbd8badac6c6bd79aa4c975a6570ded6f
report file SHA-256             ce681351c27957dc54168a987e741bdc3f5f2fcee151f5055946eac665da950f
Factorio executable SHA-256     d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b
Factorio archive SHA-256        ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2
authentication digest           d777bf268f0f0795b1d622eed07482d5cf2b3158b9edbc7c8d7c2f7ff4dd930c
instance spec digest            4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79
instance binding digest         c2f8563d7e08a6c6c6cd9a368fb88033c5f1a3e8ee76dfee8552b6d8d3820b26
instance readiness digest       0f9c22f6d9557ba3ae89196d75ea2273ed02d8d037b642638822360a5efe9e55
disposition                     superseded_before_stage
```

No coordinator stage command was invoked. Source inspection found the
v3-to-v2 filename mismatch before any revalidation-03 root or staged-candidate
binding was created.

## Stage-handoff repair validation

```text
coordinator/qualification/truth focused suite       PASS 52
project-state generation and validation             PASS
canonical plan generation and validation            PASS
schema validation                                   PASS 304
source-format validation                            PASS
strict validation                                   PASS
portable AIDE validation                            PASS
Debug native build and CTest                        PASS 57/57
full promotion Python obligations                   PASS 567
required-blocked skips                              0
unknown skips                                       0
optional skips                                      7
unsupported skips                                   2
git diff check                                      PASS
```

The canonical build-aware validation initially exposed that the default
all-target build does not include the three archive proof/fuzz executables
that the promotion Python suite treats as required. Those runs are not counted
as acceptance. The same isolated build root then explicitly built:

```text
fl_archive_probe
fl_archive_metadata_fuzz
fl_archive_plan_fuzz
```

and bound their exact paths for the final zero-required-blocker promotion
run. This validation-runner gap is separate test-infrastructure debt; the
stage-filename repair did not change `tools/dev.py`, CMake targets, archive
code, or obligation policy.
