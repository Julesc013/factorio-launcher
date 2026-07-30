# Qualification-04 producer binding

## Historical condition

The accepted producer was literally bound to:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-03
```

It therefore correctly refused a new qualification-04 task root. Running
qualification-04 without a reviewed source update would either fail or require
an unqualified ambient workaround.

## Bounded source update

The producer is now literally bound to:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04
```

It continues to derive the task identity from the exact absolute task-root
name and refuses the historical qualification-03 root. No CLI or environment
override was introduced.

Qualification-04 emits new versioned bindings:

```text
qualification binding schema
facman.play_candidate_qualification_binding.v3

qualification report schema
facman.instance_isolated_candidate_qualification.v3

target evidence WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

The accepted v2 schemas remain unchanged and continue to describe the
historical qualification-03/revalidation-02 chain.

The source update reached reviewed remote `dev`:

```text
task revision
c8bc937f1190d1068745a255b9d28ff24a499c0c

PR
#99

dev integration
569883a86c50ca203ccbecec6d37216f22f7c6a0
```

The exact PR head and integrated `dev` passed CI, schema, code-security, and
security-policy workflows. Fresh remote source closure and a diagnostic
qualification then proved the producer and v3 schemas, but the coordinator
stage handoff was stopped before invocation because it would have copied the
v3 binding under `qualification-binding.v2.json`.

That diagnostic chain is preserved and superseded before stage. It is not
silently reused after the coordinator repair.
