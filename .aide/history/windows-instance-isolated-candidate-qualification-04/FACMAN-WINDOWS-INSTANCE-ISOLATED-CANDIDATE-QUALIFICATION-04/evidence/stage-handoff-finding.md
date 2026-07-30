# Qualification-04 stage-handoff finding

Date: 31 July 2026

## Finding

The integrated qualification producer correctly emits:

```text
qualification-binding.v3.json
schema facman.play_candidate_qualification_binding.v3
target FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

Before invoking coordinator `stage`, source inspection found that
`instance_isolated_verdict_coordinator.py` selected this fixed destination:

```text
artifacts/qualification-binding.v2.json
```

The native evidence copy would have preserved the bytes and hash but
misrepresented their version in the staged filename. Because the coordinator
configuration makes that copied path authoritative for later steps, this is a
source-bound stage-closure defect.

## Disposition

```text
remote source closure        pass
diagnostic qualification     pass
coordinator stage            not invoked
revalidation-03 root         absent
staged candidate             absent
prepare                      false
WPR/observer                 false
Factorio execution           false
human verdict                unset
authority                    unchanged
```

The diagnostic qualification remains immutable and is
`superseded_before_stage`. It will not be repaired, renamed, copied into a new
stage, or otherwise reinterpreted.

## Bounded correction

The coordinator owns one explicit immutable destination filename:

```python
QUALIFICATION_BINDING_FILENAME = "qualification-binding.v3.json"
```

The stage regression proves:

1. the generated coordinator configuration points to this filename;
2. the v3 copy exists;
3. the historical `qualification-binding.v2.json` path does not exist.

No dynamic filename selection, schema migration, ambient override, observer
change, route change, or authority expansion is introduced.

## Required regeneration

After reviewed remote integration:

```text
new empty remote-source roots
→ fresh clean build
→ fresh qualification-04
→ fresh revalidation-03 root
→ coordinator stage only
```

The first diagnostic closure, build, and qualification are not reusable as
the repaired evidence chain because the coordinator source revision changes.
