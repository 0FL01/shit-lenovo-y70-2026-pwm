# Exact selector initial snapshot boundary

Base:1612f970e1cdad38c01e967fad014733b8aeebe6. This is an offline source
correction, pending independent implementation review and physical
requalification. No device execution, deployment, Git mutation or WORKSTATE
write is included. No private raw capture is published with this change.

## Actual saved failure and scope

Authorized saved0171 from original e0fb was verified and replayed against that
original validator. Its234-event before-prefix was unchanged. Entry count27→34
matched exactly seven (pending0,length11,flags0) page callbacks. Controller
count180→191 contained one leading native validate_status rc1 followed by the
exact ten selector controls; there was no trailing extra event. CHILD returned
correct selector values and rc0. The original validator therefore correctly
rejected its mismatched outer interval.

That leading return preceded the first selector entry. Return ordering does not
prove issuance order, completion of the whole ESD checker, absence of overlap or
physical recovery. The old local gates imply that return was already included
in the child's initial controller baseline. However, that initial snapshot was
not emitted: the actual saved run cannot retrospectively qualify under the new
contract. Its missing-snapshot rejection was explicitly checked, without
inventing or splicing a replacement snapshot.

The1612 change closed the independent restoration-side window by holding mode5
through host validation. It remains intact but was insufficient for this leading
observation-boundary mismatch.

## New contract

The child publishes exactly its existing $S after initial awk/prefix checks,
before isolation, first DSI, or overwriting that file. It does not recapture the
trace. A decimal byte length and unique SELECTOR_INITIAL_BEGIN/END framing bind
the exact UTF-8 payload. A failed wc/cat, missing/duplicate/truncated framing,
NUL, unknown non-header initial trace line, or exceeded bound fails closed.
The initial snapshot cap is4MiB minus1024bytes; total CHILD remains bounded at
4MiB. The reserve covers fixed framing and the exact five selector output lines.
No transport or envelope cap is increased.

The host applies the existing validate_safe_gap to outer TRACE_BEFORE→published
initial snapshot, then the unchanged exact selector delta to initial→TRACE_AFTER.
No leading event is subtracted by timestamp/order. Structured gap events, both
snapshot SHA256 identities, event counts, source labels and entry-count linkage
are required under aa_selector_initial_snapshot_v1 in runtime, acquisition and
stock qualification. Exact raw bytes remain in the private envelope evidence.
Old raw/report contracts are rejected, not silently upgraded.

The1612 mode5 lifetime, native/state/boot/ownership checks, validated pre-restore
cursor, mutation=True restoration, pending-read latch and caller-owned
panel_uncertain are unchanged. Host rejection occurs before restoration or any
next action and retains reboot recovery. The final cursor retains all events.

A generated-shell fault test also exposed an older empty-trace corner: awk's
uninitialized control count printed an empty string, which could skip the first
numeric oldc gate. Printing c+0 now supplies an explicit zero. This strengthens
that gate without changing nonempty counts; actual0171 had180 controls and was
not caused by this corner. Both empty and nonempty after-snapshot injections
are covered.

## Residual scope and cost

The existing pre-child remote guard and per-operation checks remain. The interval
between that guard and the initial snapshot is still classified by the host,
not by a new remote classifier before first DSI. Unknown activity there can
therefore be rejected only after CHILD returns. This correction provides an
explicit observation boundary, not atomic first-dispatch safety, cancellation
of in-flight ESD work, or a general concurrency guarantee.

No new trace capture, sleep or host roundtrip is added. Snapshot publication
adds payload/formatting cost; physical latency is unmeasured. Limits remain
37/45/8/60/600seconds with unchanged recovery, camera and identity gates. Fresh
same-source physical stock requalification remains necessary. No new mandatory
hardware criterion or physical PWM/AA-readplane claim is introduced.

## Verification

The dedicated suite exercises real generated-shell before/after-snapshot
injections, exact known-poll admission only before the snapshot, unsafe/unknown
prefix and trace rejection, byte framing, cat/wc/oversize failures before
isolation, no extra capture/wait, retained provenance, legacy rejection,
restoration exclusion and sticky no-next-action behavior. Existing restoration,
source-tamper, acquisition and optical suites remain included. All fixtures in
this change are synthetic; existing historical scenes stay external/private.

Final executed counts, command sizes and file identities are in
../../aa_timed_runtime_closure.json under selector_initial_snapshot_correction
and SOURCE_FREEZE.json beside this file. Earlier closure records describe their
own revisions and are not qualification of this one.
