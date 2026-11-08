# Read-only Android capability inventory

Status: **confirmed-on-target inventory only**, not behavior qualification or
permission to launch the fixture batch. See [sanitized observations](result.json).
The sequential run completed on 2026-11-08 at 22:36:11 UTC: 27 read-only calls,
4514 accepted response bytes, no uncertain command outcome.

Existing-server/version preflight and fresh immutable target/camera binding passed.
Exact target build/slot/kernel/device, BOE-v4 panel, module hash, existing root and
Enforcing matched the qualified runtime. The camera was only identified through
three getprop reads. Target boot was unchanged and the research mutex absent before
and after. No target lock was acquired or removed, no device files were written,
and no experimental DSI, settings, camera capture, tracing, signals or reboot ran.
Current brightness/settings were not measured; this is not a new restore claim.

The UID2000 shell resolves awk, timeout, setsid, ps, stat, df, sh and sha256sum
under /system/bin. kill resolves as a shell builtin/name, so it was not executed.
Separate read-only ulimit -Hf and -Sf queries returned unlimited; units remain
unqualified and neither limit was changed. Each command-v query was checked
individually. No aggregate command-v status was used to infer all tools exist.

Help was requested only from resolved trusted system executable paths. setsid,
ps, stat and df returned zero. timeout --help returned125 with665 bytes of usage
text: recorded as unsupported-or-unknown, not a timeout success or cancellation
proof. ps help did not establish both PGID and SID field support; their absence
from this text does not prove the fields unsupported. Utility-help text remains
private; the public report records only paths, sizes, statuses and narrow flags.

Reads used the existing [guarded transport](../../06-tools/guarded_adb_socket.py)
after [remote preflight](../../03-investigation/adb-remote.md). Identity predicates
match the qualified stock runner. Utility queries were id -u; separate command-v
for the nine names above; the two ulimit queries; and separate --help calls for
timeout, setsid, ps, stat and df. Per-response caps were16–8192 bytes and the
aggregate acceptance cap64KiB. These are host acceptance limits, not a remote
process-cancellation or storage boundary.

The [portability plan](../android_validator_portability_plan_20261108.md) still
needs an independently reviewed complete batch lifetime, process reconciliation,
aggregate storage and exact owned-cleanup contract. This inventory establishes
neither those properties nor clock-rate/suspend behavior, Android max-cap costs,
sequencer readiness or physical PWM frequency. Unknown P85=14 remains disabled.

## Independent evidence consistency and limitation

Independent comparison matched all 27 retained raw streams and their sizes
(4514 bytes) to the public observations. Acquisition ran from
22:35:54.674177 to 22:36:11.366415 UTC on 2026-11-08. Raw streams alone do not
prove the command text, return codes, ordering or guarded acquisition: the
original acquisition was inline and no complete acquisition script/log was
retained. Those details remain the acquisition report, not independently
reconstructed proof from raw bytes. This is an evidence-provenance limitation,
not a detected data mismatch. Public result.json is unchanged.
