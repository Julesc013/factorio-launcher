# Gate 4C observer-start live proof

Date: 2026-07-24

## Result

The corrected clean commit
`83a07bc30d37624c02a63c11857a4071e5f88d6d` passed the elevated
observer-start-only comparison.

Both paths passed:

1. the Python observer boundary directly; and
2. the same boundary launched through the native FacMan process supervisor.

For each path:

- provider revision `gate4c-etw-file-registry-process.v5` was valid;
- WPR was idle before start;
- WPR reported recording in progress after start;
- the live WPR status reported zero dropped events;
- WPR stopped successfully and saved an ETL trace;
- post-probe status reported that WPR was idle;
- the committed tooling identity was clean and hash-closed; and
- the structured probe contained no errors.

The native supervisor additionally reported:

- process termination `exited`;
- exit code and native status `0`;
- an empty stderr stream;
- process-tree termination complete;
- native job containment active; and
- a PID-reuse-resistant process identity.

No permit was constructed or issued. No Factorio process was started.

## Evidence

The external append-only artifacts remain under:

```text
E:\Temporary\FacMan\
  FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01\
    evidence\observer-start-probes\
```

| Artifact | SHA-256 |
| --- | --- |
| `comparison-20260724t071048z.json` | `29fbfddbad0933af1fc5353e71d312fef9afec640172e1291135297d3f7bd9df` |
| `comparison-20260724t071048z-transcript.txt` | `4c6281060bfc3498f1323eb392cab2eeb16b1f30a4a99d326cbd73ec366300d8` |
| `gate4c-observer-start-probe-direct-20260724t071048z.json` | `2c45cd04163a6fe692dddc25d50fe4fa3586607f5fe8f15d9446ec52844590b5` |
| `gate4c-observer-start-probe-native-20260724t071048z.json` | `52c09d77f1ac0a77c208f393a194b8611d8669492304144c9d1ba612f79d8dca` |
| `gate4c-observer-start-probe-native-20260724t071048z-native-supervision.json` | `978b43941d103f15bab1d6bd60bdcaaf629093d87bce02cf686bed8ad67646e5` |

Direct probe:

```text
probe digest  9d84ff0ea23966dbbbdfa708f5e34e5c74edab6bef30193ed6fa47f198e75e2b
trace digest  c831f22dfa2bed602d4c00b70b7a8990e6f009482279e3af0647d0675dc114c1
```

Native-supervised probe:

```text
probe digest  d4a9bac33949cc5ff1a2bfe4f5ab02e6423e61d73ac5bce631d947207ff77e5b
trace digest  61cf46a8444507407aabfd5a2f9c5628d0a8bb7e4da0c33baed1ad672f0b9891
```

## WPR and WPA boundary

Windows Performance Recorder (WPR) owns capture. It enables the frozen ETW
profile before the supervised process boundary and writes the resulting ETL
trace under the task-owned temporary root.

Windows Performance Analyzer (WPA) is the interactive trace viewer.
`WPAExporter` is the deterministic command-line export path used by the
evidence tooling. They operate on the saved ETL after capture; they do not
provide launch authority and are not background recorders.

This observer-start proof establishes that capture can become active through
the real native supervision boundary and can be closed without residue. It
does not establish a Gate 4C human verdict or prove a real Factorio process
tree. Those remain part of a fresh verdict attempt after repair closeout.
