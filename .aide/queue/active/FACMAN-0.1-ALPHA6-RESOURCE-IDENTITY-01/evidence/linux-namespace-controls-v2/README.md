# Recorded Linux namespace controls

Eight fixed synthetic controls passed on the recorded local WSL host. ROOT independently verified eight case records, 79 raw originals, 28 exported regular files and the complete 2,983-row observed union. This evidence leaves the resource WorkUnit active/PENDING.

| Control | Recorded outcome |
| --- | --- |
| Normal completion | PASS; controller exit 0 |
| Session-changing orphan | PASS; orphan retained until init exit |
| Held stdout, ignored TERM | PASS; bounded deadline, controller exit 42 |
| Worker timeout | PASS; bounded deadline, controller exit 42 |
| Init SIGKILL | PASS; controller exit 70 |
| Unshare SIGKILL | PASS; controller exit 247 |
| Case-controller SIGKILL | PASS; controller exit -9; expected peer reset recorded |
| Proc-mount refusal | PASS; exact pre-worker refusal, unarmed, controller exit 1 |

The first attempt remains failed: six controls passed, the seventh reached its intended armed controller kill but failed on ConnectionResetError(104), and the eighth was not attempted. Its outer host outcome remains UNKNOWN. Later cleanup does not convert that attempt to success. The successor catches that reset only for the armed, triggered case-controller-kill control; pre-arm and unexpected resets still fail. An unchanged injected oracle records OLD RED and successor PASS.

For the seven armed cases, the reviewed source requires registered pidfd exits and an empty retained namespace census before recording terminated_before_cleanup=true. Each case separately records quiescent cleanup, accounted scope, an alive unrelated sentinel and unchanged mountinfo. The mount-refusal case uses its own unarmed refusal oracle. No separate per-pidfd event stream, raw census listing or raw mountinfo snapshots were serialized. Audits bind the recorded assertions to the frozen source and raw outputs; they do not claim an independent replay of unrecorded events.

The admitted limits were 240 seconds overall, 20 seconds per control, 10 seconds for init and cleanup, a 3-second handshake, 1 MiB per captured stream, 4,096-byte frames and eight registered handles. Signals use owned pidfds. Synthetic workers use UID/GID 65534, no supplementary groups, no capabilities and no-new-privileges under the trusted controller. This does not establish hostile isolation or protection before arming, after guardian loss or after WSL loss.

The earlier read-only collector actually observed the missing three continuation parent rows, completing the 2,837-row baseline. Failed v1 added 68 observed rows to reach 2,905; successful v2 preserved every one of those rows and added 78. The final 2,983 map combines the guardian's 2,981-row pre-final observation with two final result/map files observed by the closed exporter. This is a source-bound observed union, not a new simultaneous root sweep. The exporter repeats bounded roster and hash checks before completion; the audits verified closed records and exact member bytes without another Linux read.

[The custody map](custody.json) binds [the deterministic archive](custody.zip). Read actual-v2/root-actual-review.json for ROOT's final qualification and actual-v2/independent-actual-review.json for the preceding audit. ROOT's receipt SHA256 is 24b63d74b924092bfc054246d141d448dbbc72777806a254cea964b7ced75cbf. The complete-map SHA256 is 4f1331262841d5413aac969a508b45f0e044d8b4720b15e5ca110183e42da345.

Each archive prefix has its original member map. actual-v1/ preserves the failed run; source-namespace-v2/, source-host-v3/ and source-export-v2/ preserve source reviews and causal tests; actual-v2/ preserves actual invocation/export records and audits. prior-complete-inventory/ preserves the baseline collector and its ROOT audit. Nested ZIPs are original byte streams; raw line endings and historical failure/unknown fields remain unchanged. The audit tool payload is retained, but its original shell-stdin transport bytes were not separately captured.

This checkpoint adds documentation and custody only. Product process suites, SDK/provider adoption, complete native/platform/hosted coverage, game and human gates, signing, release and Beta1 completion remain outside this result.
