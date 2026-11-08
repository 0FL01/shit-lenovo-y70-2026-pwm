# Stock low-brightness C1 map: tool and completed first run

Status: first live qualification completed by the coordinator on2026-11-08,
after independent review. All six captures passed the gates and were separately
revalidated offline; originals were restored and the mutex released.
See[completed run](../artifacts/stock_c1_20261108_01/run.json) and
[result/semantic limits](../artifacts/stock_c1_20261108_01/result.md).
Development/review used no devices. Existing C1,85 and A9 tools are unchanged.
Camera is never bound or accessed by this tool.

## Question and exact scope

Map qualified C1 at stock DC0 through native DBV:
**828 →460 →2048 →3000 →3600 →828**, with one identical native120-family timing
tuple throughout. The final828 must reproduce the initial C1 bytes.460 is the
selected DT minimum;64/256 are not included as ordinary stock-range points.
3601 is not part of this first pass. No85/C1 parameter write or DC table is sent.

The known control is C1=`00 00 60` at3600/120 and `00 00 10` at3646/120.
The completed A9 comparison separately found`0060→0010→0060` at3600; its meaning
is not decoded. The new low-stock sweep found brightness-dependent values up
to0002C0, including nonzero low nibbles. These are not established counts or Hz.
Width/duty/aggregate timing remain hypotheses. Preserve all three returned bytes;
framing does not establish that they form one24-bit field. BE24 is only a numeric
presentation. Do not use`BE24>>4` as a general frequency decoder or claim≥2000Hz.

## Invocation

Use the current verified private ADB socket and fresh, currently bound target ID:

```
PYTHONDONTWRITEBYTECODE=1 python3 06-tools/stock_c1_sweep.py TARGET_ID \
  --experiment-id NEW_UNIQUE_ID \
  --output artifacts/NEW_UNIQUE_ID --offline-check
```

Replace`NEW_UNIQUE_ID` with a fresh lowercase ID matching`[a-z][a-z0-9_]{7,63}`;
the completed ID stock_c1_20261108_01 must not be reused.
Remove`--offline-check` only for the coordinator's approved execution. Existing
output/private directories or retained markers with this exact ID cause refusal.
Do not reuse an ID after a failed/uncertain attempt. No automatic read retry.

Require pre-existing manual brightness, awake screen, software120, DC0, stock
ESDreg_read, root, Enforcing, exact panel/build/slot/kernel and SHA-pinned module:
`1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804`.
The coordinator must establish returned stock state before starting; software
DC0 alone cannot prove every hidden DDIC register is stock.

## Lifecycle and evidence

One root-owned0700 shared mutex with0600 owner token is held for the entire run;
each C1 child joins that token. No stale unlink. Original Android brightness,
brightness mode, min/peak refresh, timeout, native DBV and logger bit are saved.
The current serial binding and boot_id remain private; public evidence contains
only verification outcomes. The private owner token allows exact recovery.

An independent600-second device watchdog is armed before mutable setup. Logger
is enabled; timeout is raised to at least10minutes without reducing a longer
original value. One HOME + explicit stock Display Settings launch establishes
real activity (already-awake WAKEUP alone previously failed to undo dimming).
Awake/unlocked policy is verified, then exactly one stock90→120 settings
anchor is requested. Fresh native mode events must prove both transitions.
Native120/group3 or the already-audited120-family idle1/group8 is accepted at
baseline, then the exact tuple must remain unchanged at every sample.

At each point, one standard native brightness write is made. Held sysfs DBV and
matching logged`51 hi lo` transport are checked (a same-value cache hit can omit
the packet). A two-second quiet interval must contain no native DSI writes or
mode transition. No per-point settling retry is made after the initial reference
is established. Quiet checks are not an atomic compositor lock; unexpected
concurrency fails closed. The initial Settings scene is then left static; no
per-point UI/redraw or camera action is performed. The original foreground app
is not claimed to be restored.

Each fixed C1 maximum3 request uses the qualified16-byte scratch path and must
pass the existing long3 header/WC/ECC/raw-count/return validator. Extra entry
probes and in-device gates qualify standalone flags/pending state and prevent
continuing after a native TX failure that userspace printf cannot detect.
Public per-point JSON is reserved before the read; raw stdout/stderr are saved
privately before validation, under`~/.cache/legion-y70-stock-c1/EXPERIMENT_ID/`.
Transport interruption may prevent complete raw capture and remains uncertain.

## Crucial TX-bytecount audit and failure handling

Exact module `_sde_debugfs_conn_cmd_tx_write` at.text0xe7cfc, saved Ghidra12.1.4
bounded callback excerpt: callback at connector+0xc00 returns native status,
success is saved at+0x12f1, but the write returns the input bytecount regardless.
Therefore successful printf alone is insufficient to authorize the next DSI.
The rx writer saves the actual callback return and rejects nonpositive results.

The isolated adapter adds gates at empty-start, after page23, after read, after
body page0, before cleanup page0 and after cleanup page0. Required controller
prefixes are`[]/[0]/[0,3]/[0,3,0]/[0,3,0]/[0,3,0,0]`; page callbacks are
standalone pending0/length11/flags0. Gates require zero probe misses, exact
trace/profile counts, unchanged event prefixes, exact event order and matching
PIDs. Header/helper are qualified before any page0 following the read. Missing,
extra, malformed or negative evidence aborts before the next DSI operation.

On a failed in-device status/gate, cleanup may remove its own trace/probes and
mount namespace but does **not** append page0 or re-enable ESD. The outer process
does not issue brightness/settings/DSI recovery into an uncertain queue. It makes
one ordinary reboot request to the same captured serial, then read-only polls
for a changed boot_id, completed boot, exact identity/root/Enforcing, mutex owner,
DC0 and ESDreg_read. Only then may settings restoration begin. Read/transport or
host-validator failures abort the sweep; no next point is executed.

Native anchor and brightness-dispatch failures also latch recovery before any
settings restoration. Original settings, raw native DBV (including delayed stability), awake state and
logger are verified before watchdog disarm, owned-temp removal and mutex release.
Null settings retain delete semantics; refresh restoration ordering respects the
current ceiling. Restoration failure preserves ownership and watchdog evidence,
but the public watchdog_state distinguishes a verified armed process, uncertain
disarm, and an inactive original watchdog after a verified reboot. A retained
armed directory after reboot is not an active watchdog.
If reboot cannot be verified, no further cleanup writes occur. A disconnected
watchdog can reboot but cannot restore Android settings without the coordinator;
the saved originals must be applied after access returns. Never report that as a
completed restoration. Hard kernel hangs/panel damage can defeat reboot recovery.

Residual driver risk remains: malformed long0 can panic in the stock parser
before any userspace gate. The adapter cannot repair that driver. In-device
guards reduce continuation risk; they do not guarantee hardware safety or freeze
the compositor. No long40 census or request1 fallback exists.

## Offline checks

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools -p test_stock_c1_sweep.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools -p 'test_capture_ddic_*.py' -v
```

The sweep tests execute the actual adapted shell with fake temp files/transport
effects, injecting shell/native failures at all four DSI operations, HUP/TERM,
bad headers, probe misses and changed trace prefixes. They also check exact
successful framing, native DBV logging/tuple stability, no writes while uncertain,
changed-boot verification, restoration-failure ownership and offline/no-overwrite
behavior. These fault-injection tests are offline; the successful first live
wrapper qualification is the separately linked run, not a live failure test.
The completed local checks are12 new tests plus18 unchanged C1/85 tests. Execute
orchestration fixtures additionally cover uncertain read→reboot→restore,
unverified reboot→no restoration, and a mismatched final828→failed qualification.
