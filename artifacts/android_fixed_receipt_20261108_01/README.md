# Fixed synthetic receipt acquisition: offline preparation

Prepared only. No Android execution by the author. Lead owns the single physical
attempt, after independent review of this acquisition and fresh preflight.

Default invocation (or --check) verifies source pins without creating files or
constructing a transport. Bytecode writes are disabled before imports. The sole
execution option is --execute; no command, device, path, nonce or phase arguments.
Use PYTHONDONTWRITEBYTECODE=1 python3 -B acquire.py --execute only under the lead's
approved existing guarded ADB environment. Never run the real DSI runner here.

The reviewed package pinset is
ff2e63976d1daf914b0164cb26807558451418d6bf09f1f41115e1104a264384.
Fixed BASE/epoch/nonce come from that package. Acquisition retains private actual
boot-containing rendered scripts and commands, actual streams, partial complete
frames and per-call events. Public result contains hashes/counts/flags, never raw
streams, private paths, boot or actual device identities. Command/script hashes
are frozen before the first device write. Dispatch command limit is 16 KiB;
phase response limit128 B, bounded exact reads, and host8-second acceptance deadline.
A host deadline is NOT remote cancellation. Unknown outcomes retain HOLD.

Fresh guards cover server/version, target/camera distinct identity bindings,
SKU/build/kernel/slot/Enforcing, root0 and shell2000 UIDs/GIDs, BOE panel, module,
boot, absent mutex, absent fixed BASE, root stat metadata for /data (1000:1000:771),
/data/local (0:0:751), /data/local/tmp (2000:2000:771), and plain shell inability
to write /data or /data/local while able to traverse /data/local. No ancestors
are changed. These reads are not an ACL/lifecycle or concurrent-writer proof.

The only device writing sequence is reserve as root, capture as plain UID2000,
and seal as root. After reserve, a read-only plain UID2000 access gate must
confirm source/manifest readability, BASE/source/work traversal, work writability and control read/write
denial before capture. Failure retains BASE without capture/seal or any
permission/SELinux-label workaround; the host gate latches HOLD even if a caller
catches the access failure. Capture must synchronously return exactly7 with empty outer
streams, completed transport. Seal's fixed argument7 is admitted only after that
exact actual capture tuple, never from a device status file. Every phase consumes
its host gate before dispatch, including failures caught by a caller. No retry,
adoption, cleanup or resume operation exists. Fresh result/private paths also
prevent another process invocation using this artifact after a started attempt.

Root seal must return0/exact marker/empty stderr. Independent bounded reads then
check known directories and regular files (UID/GID/mode/link count/length), exact
producer and manifest, published binary bytes, completion marker and complete
receipt including private boot, fixed epoch, source/manifest hashes and actual7.
UID2000 then must fail read/write access to root control/receipt and write access
to source files, which root has already confirmed exist. Final boot/mutex/Enforcing
checks precede COMPLETED_SYNTHETIC_EXPECTED_NEGATIVE. This does not mean producer
success, controller admission, DSI execution or PWM success.

All root BASE/source/work/control/receipt names are intentionally retained as small
owned spent state. No claim that everything was cleaned. Source/control isolation
assumes trusted host/root and no competing writers. It is not absolute immutability,
a durable ledger, crash recovery, power-loss protection or proof of process lifetime
for arbitrary producers. Only this fixed finite builtin-only producer is in scope.

Offline checks (19 each normal and -O):
PYTHONDONTWRITEBYTECODE=1 python3 -B test_acquire.py
PYTHONDONTWRITEBYTECODE=1 python3 -O -B test_acquire.py
Tests use fake sockets/outputs/status only; no ADB/device I/O. They cover check mode
no writes/transport, pin mismatch, fixed rendering, command cap, invalid boot,
receipt bytes, ordered gates, status/output mismatch, caught/unknown failure,
no retry after out-of-order calls, pre-capture access denial/nonempty streams
preventing capture/seal in fake end-to-end acquisition, shell binary framing, cap-before-payload,
complete-frame partials and pre-read/late-recv deadlines. These are focused tests,
not a repeat of runtime qualification. Existing runtime13 and 37/45/8/60/600
history remain unchanged; no14 admission.
