# Qualified page23:85 diagnostic, not a PWM setter

Status: offline implementation and exact-target parser audit. This document does
not establish a live read result or authorize any write to85. The stock init
contains15, but a read plane need not equal a written configuration plane.

## Why maximum3 for an actual one-byte observation

The request uses MRPS3 and the existing, qualified16-byte receive path. Acceptance
requires an actual DCS short1 response: DT21, one payload byte and one controller
return1. It does not call85 a three-byte register, accept padding, or reuse the
C1 long-response validator. Short packets contain their payload in the header
and have no separate payload CRC.

Exact saved msm_drm.ko SHA256:
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
Saved Ghidra12.1.4 controller/helper/rx-write excerpts plus pinned LLVM disassembly:

- `.text197184..1971fc`: request1/2 allocates4; request3 allocates16, width16,
  MRPS3. Request3 has one helper call, no repeated-store loop.
- `.text191678..191690`: the helper normalizes raw13 to9 at width16/MRPS3.
  For a short response raw4 remains4. Raw8 is NOT normalized to4 on this path,
  unlike width4, so an ACK-prefixed short response is deliberately rejected.
- `.text19752c..197554`: normalized count4 and request3 select scratch+12.
  The header probe reads exactly bytes12..15, within the16-byte allocation.
- `.text197630..197664`: DCS short1 copies byte1 of the aligned header and
  sets actual return1 even when requested maximum is3. The debugfs rx writer
  saves the callback's actual return as its response length at connector+13f4.
  `_sde_debugfs_conn_cmd_rx_read` loops over this same actual length, printing
  one byte for return1, rather than printing the full requested buffer.
- `.text1975f8..197628`: a long response copies the requested3 without checking
  word count. Valid long1/2/3 fit this scratch but may include CRC as apparent
  data, so none are accepted. Malformed long0 leaves2 bytes and can invoke
  fortify panic before userspace validates anything.

Request1 was not chosen: it allocates only4, so ANY packet parsed as long leaves
no space after the header and can panic on copy1. Maximum3 reduces that risk; it
does not eliminate malformed-response, unexpected hardware or hung-kernel risk.
MRPS can influence the panel's response format/length. A long response or an
ACK-prefixed short response will fail qualification, not trigger an automatic
retry with a different request. The tool does not modify the loaded parser.

## Invocation and evidence

After current private-ADB preflight and target identification, the coordinator
prepares stock DC0, native DBV3600 and software120 independently. These are checked,
never silently changed. Example syntax, with the freshly verified target ID:

```
PYTHONDONTWRITEBYTECODE=1 python3 06-tools/capture_ddic_85.py TARGET_ID \
  --dbv 3600 --refresh 120 --output artifacts/NEW_UNIQUE_P85.json --offline-check
```

Removing `--offline-check` executes one diagnostic. The tool sends page23,
`3 0x06 1 0 1 0 0 1 0x85` to rx_cmd, then page0 and cleanup page0. It cannot
write85, take a different register argument, change brightness/refresh, or reboot.
The current C1 tool/interface remains unchanged. Its reviewed lifecycle shell is
adapted with fail-closed exact replacements, using distinct trace/work names.

The same root-owned0700 mutex with0600 owner token, exact target/build/module
guards, private tracing/mount namespace, newline-terminated ESD switch/readback,
30-second timeout with3-second kill grace, traps and page0/ESD restoration apply.
`capture(..., held_token=...)` can join a verified parent token without releasing
its lock. Standalone releases only its own lock after clean completion. No stale
unlink, daemon startup, alternate transport, fallback query or retry exists.

Raw stdout/stderr are preserved0600 in `~/.cache/legion-y70-p85/NONCE/` before
framing validation. Public JSON reserves the attempt before external action.
Existing output is refused. Failure/uncertain transport requires coordinator
inspection and independently verified page/ESD/lock recovery, not blind retry.
Timeout/traps cannot guarantee recovery from a hung kernel or hard kill.

Acceptance requires exact target identity and state, header/helper/read-return
same PID, header DT21 with reserved byte0 and valid ECC, payload equal to the
single printed byte, request/MRPS3, scratch/helper16, raw/normalized count4,
controller returns exactly`[0,1,0,0]`, page returns exactly`[0,0,0]`, no lost
trace/probe misses, and verified ESD/cleanup. Separate printf PIDs for page writes
are expected. Read values are not restricted to15; no PWM or writability claim
follows from any value.

Offline tests:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools -p 'test_capture_ddic_*.py' -v`.
The new tests cover all256 payloads/ECC, wrong packet types/counts/widths, ACK8
refusal, duplicate/missing events, exact returns/PIDs, lifecycle/shell syntax,
inherited locks, template drift refusal, no-overwrite under Python-O, and the
conditional scratch bounds. Module/probe template drift also fails closed.
The mocked transport test verifies raw evidence survives failed validation and
there is only one attempted query. All18 tests (9 new +9 unchanged C1) pass.
No physical action is part of those tests.

## Existing live long3 response, separately qualified offline

The coordinator's first stock828/120 diagnostic (nonce05f192fe7990) returned
`15 00 00` as a DCS long3 response, not short1. The short-only validator correctly
rejected it, and the failed attempt remains unchanged at
`artifacts/p85_live_20261108/stock828_qualified.json`.

Separate offline result: `artifacts/p85_live_20261108/stock828_long3_reanalysis.json`.
The original private raw evidence passed the existing long3 packet validator
after adapting only the output label, plus independent exact event accounting:
header`1c 03 00 16`, WC3/ECC valid, request/MRPS3, scratch/helper16,
raw/normalized9, one receive, matching read PID, controller`[0,3,0,0]`,
page returns`[0,0,0]`, exact probe hits1/1/4/3 with zero misses, and verified
ESD restoration/cleanup. The strict short-reader rejection was rechecked.
No command was replayed and no device was accessed for this qualification.

This establishes that the first returned payload byte is15 under this request,
consistent with the init value. It does not establish register width, whether
the trailing zeros are padding, read/write plane identity, writability or PWM
frequency. Header framing distinguishes the three payload bytes from CRC;
the payload CRC itself was not captured. No request1 retry or85 write is implied.

## Later TX failure-path audit

The exact module's TX debugfs writer returns the submitted bytecount regardless
of the native transfer callback's success, storing that success separately.
This standalone85 helper inherits the historical C1 cleanup: actual return
validation occurs on the host only after cleanup, so shell success alone cannot
prevent an extra page0 after a native TX failure. It does not provide the later
in-device continuation gates implemented by`stock_c1_sweep.py`.

The existing stock828 long3 observation is not invalidated: its saved native
returns were independently verified as`[0,3,0,0]`/`[0,0,0]`, with successful
cleanup. Keep that evidence and the original strict short-only contract intact.
Future diagnostic workflows need the gated failure-path design, not a blind
reuse of standalone cleanup as recovery for an uncertain queue.
