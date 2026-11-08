# Offline local validator feasibility spike

NOT a controller, device-qualified executable, admission gate, or permission to
perform DSI. No live CLI or child execution exists. Existing qualified source is
unchanged. Unknown14 is unsupported. This is deliberately incomplete.

The portable capture validator reads bounded owned regular files, never evidence
through shell variables. A caller supplies stdout, stderr, nonce, kind and child
status. It rejects nonzero status, stderr, symlinks, non-0600 files, another UID,
multiple hardlinks, >256 KiB capture, NUL/non-ASCII/control bytes. ASCII TAB/LF and
printable ASCII is an explicit stricter subset of strict UTF-8, matching all saved
valid captures. It must not be described as equal acceptance to the Python oracle.
Exact trace order/counts, field sets/duplicates, PID correlation, profile lists,
gates, ESD cleanup order and response length are checked. Fixed 0x1600031c exactly
encodes DT1c/WC3/ECC16; accepting only that header is equivalent to evaluating ECC
for the sole permitted DT/WC. Raw high word 9/13 and request3/allocation16/count9/
MRPS3/read16 are required. CRC bytes themselves were never captured. A driver
long0 panic occurs before these validators and cannot be prevented by this port.
The writer validator never treats tx-write bytecount as native success.

writer_wire.awk separately checks the exact stock15 wire sequence within the
writer markers, no traffic from protected origin to begin, pinned native120/group3
anchor before protection, no transient native transition, failure or LOST, and
no activity after END through dump. Marker arguments require external binding.
It is an AWK fragment, not an independently safe file-ingestion entry point.
Relevant writer lines now have anchored operation-specific grammars: standalone
printk marker lines; the pinned drm/msm native mode line with one complete tuple;
and one dsi-ctrl-1 transfer per packet line. No greedy prefix removal is used.
Native alternative prefixes and extra tuples invalidate the anchor; packet
prefix/field case and spaces remain exact, while payload hex may vary in case.
Several markers or transfers on one line cannot hide behind the final suffix.
Unrelated kernel messages remain outside the operation grammar, but any protected
mode/failure/LOST/transfer or marker occurrence is still considered. The narrower
accepted printk format is deliberate and is not a general kernel-log decoder.

state.awk ports independent snapshot content semantics for DBV/DC/power/Enforcing,
refresh, boot match, empty owner-check output, and independent ESD reg_read. It
does not itself execute or authenticate those checks, validate exit/stderr, or
provide byte/file/section ingestion. Empty owner output alone proves no ownership.
Capture structured output is a projection (data/raw count/refresh/callbacks), not
the full host result schema. The caller must still compare factory P85 [21,0,0]
and C1 [0,0,96] at the required observation stage; arbitrary framed payloads are
parsed, not silently labeled factory success.

The accepted textual dialect is intentionally narrower than every string the
Python validators may parse. Every nonblank line is matched against an anchored
whole-line grammar BEFORE extracting values: canonical unsigned decimal tokens
(no leading zero except0); exact decimal entry fields in pending/length/flags
order; fixed ordered fields and single ASCII spaces after the event symbol;
printf-positivePID, three-digit [CPU], d.... or d..1. flags, decimal timestamp,
and the exact event token. Only the six pinned native symbol strings and the
explicit synthetic '(symbol)' fixture are supported. Metadata uses exact labels,
order and single ASCII spaces; profile columns use ASCII spaces, canonical counts
and zero misses. Optional parenthesized task-group/PID forms, arbitrary task names,
other symbols, TAB separators and untested trace layouts are rejected.

Trace comments are NOT generally skipped: capture.awk contains the finite exact
pinned nop/header/legend lines, the kind-specific9/9 or12/12 #P:8 count line,
plus one short synthetic legend. Any other comment fails closed, including
comments hiding cleanup/boundary/event tokens. Blank lines alone permit TAB.
Hex response bytes accept one or two digits and either case; non-entry hex fields
use lowercase0x prefix. ASCII and final LF remain mandatory. These are explicit
narrowing choices, not claims about all valid Android trace presentations.
The target contract is strict-subset acceptance on this supported dialect;
passing corpus/fault tests is evidence, not a proof of universal equivalence.
Positive synthetic cases vary payload bytes00/0A/0F/7F/80/AA/FF, raw9/raw13,
PIDs, CPU, timestamps and legitimate trace headers and compare decoder output
with Python. Factory-value policy stays outside this generic transport decoder.

Important remaining gaps: trusted fresh state/owner/boot/identity acquisition,
and stdout boundary/source/nonce provenance binding;
PRE_GUARD timing and stale marker collision checks; read-wire/native intervals;
camera barriers and optical validity; monotonic deadline and reserved-return
calculus; watchdog lifecycle and restart/termination/crash handling. These are
MANDATORY gates, not deferred-to-host-after-next-child checks. No next child may
run based on this spike. Filesystem race resistance requires a fresh immutable
owned staging directory and frozen source manifest, not just stat checks. This
spike does not implement secure staging, source verification, or cleanup.

Portable operations already occur in successful source: sh, awk, tr, cmp, stat
(%u/%a), id, wc, dirname-like path handling. New assumptions requiring target
capability qualification: stat %h, tr octal range interpretation, mktemp -d,
LC_ALL=C byte handling and actual Android awk numeric/regex behavior.
Host execution is only feasibility evidence; there was NO device access. AWK
uses no bitwise extension, strtonum, match capture array, or interval quantifier.
Filtering and LF normalization use owned temporary files, separately checked
producer status/stderr and cmp, rather than a pipeline hiding producer failure.

## Future stock-only state diagram (design only)

Verified source + fresh owned workspace + unchanged child bytes
-> host camera and target baseline qualified
-> start37s active window BEFORE arm construction/request
-> independent60s watchdog armed/verified (no renewal)
-> fresh guards + elapsed/suffix admission within37 active of45 total,8 reserved
-> one unchanged stock15 child
-> exact local capture + independent ESD/state/owner/boot/native/wire/tail gates
-> host camera_start acknowledged
-> full4.5s hold, return-prequiet overlap only when fully validated
-> host camera_end acknowledged +120 advancing sensor frames
-> fresh complete local guards + finite reserved full-return suffix
-> unchanged return15 child -> exact local gates
-> return P85/C1 + all independent guards -> verified disarm
-> final optical hold + encoded60/PTS qualification + full owned cleanup.

Every arrow requires exact bounded evidence before the next child. Any unknown
outcome, lost log, timeout, failed guard, invalid ownership or transport ambiguity
goes to reboot-only recovery. Never blind15/page0/retry. Host timeout does not
prove remote cancellation. A future locally verified autonomous factory return
on host loss may be a separately reviewed recovery path only, NEVER optical
success; it is not implemented here. Camera is another phone and cannot be
silently represented by target-local timers. No daemon, credential, autostart,
UI or watchdog renewal is proposed. Optical recovery and software safety
recovery must remain separate success conditions.
