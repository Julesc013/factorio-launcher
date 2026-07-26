# Validation

Status: PASS.

The repair changes only provider revision evidence inputs. It does not alter
either frozen policy, issue a permit, execute Factorio, record a verdict,
accept a route or promote product authority.

Candidate projection now reads both provider revisions from the generated
build identity:

```text
universal_launcher=7fc25340623131ba86c08dca4fb8a43b18a4520d
universal_setup=3f8489275077347c2918f3bb03614ec6431362ff
```

Both the hermetic evidence requirements and the instance-isolated evidence
requirements hash those generated values. No historical first-party revision
literal remains in candidate projection.

Validation:

- focused native build: PASS;
- `flb_factorio_launch_permit_smoke`: PASS;
- `facman_hermetic_play_candidate_smoke`: PASS;
- `python -m unittest tests.test_instance_isolated_play_candidate`: 5/5 PASS;
- `python tools/instance_isolated_play_candidate_check.py`: PASS;
- `python tools/strict_check.py`: PASS, 298 schemas;
- `python tools/project_state.py`: PASS;
- `python .aide/scripts/aide_lite.py test`: PASS;
- hermetic policy digest remains
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- instance-isolated policy digest remains
  `8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432`.
