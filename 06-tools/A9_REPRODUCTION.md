# Fresh A001 A9-only reproduction (not a PWM-frequency proof)

`run_dsi_mode_trial.py --a9-reproduce` is isolated from historical modes and
results. It sends the complete pinned stock DC-OFF table, exactly that table
with byte offset 68 (page 0x23, A9) copied from native ON (0E→8E), then the full
stock table. No other candidate byte changes. Both source tables are pinned.
Each phase retains five native-batch chunks, pending/length/flag trace checks,
all 75 controller packets, nonnegative return checks, short A9/9D/DBV readback,
ESD restoration and a seven-second hold in one continuous video. Hold-boundary
kernel markers reject interfering native DSI writes, and a second short readback
confirms A9/9D/DBV after each hold. Every phase first opens the dynamically
located native Screen timeout chooser and cancels it without selecting a value.
The existing 600000ms timeout and chosen native DBV must remain unchanged.
Separate redraw markers reject native DSI activity before accepting the phase. The shared atomic device mutex
`/data/local/tmp/legion-pwm-research.lock` excludes another cooperating runner;
it is never removed as stale and is released only after safe cleanup.

## Required record and invocation

The coordinator records the owner's actual applicable mission authorization
in a new private JSON, not a copied/consumed experiment. This is a scope record,
not a requirement to ask again where the owner already authorized the action.
Required keys:

- experiment_id: fresh lowercase identifier, 8–64 characters, letters/digits/underscores
- mode: `a9_reproduction`
- candidates: `["a9_only"]`
- sequence: `["stock", "a9_only", "stock"]`
- program_sha256: stock and a9_only hashes calculated by `a9_reproduction.programs`
- native_dbv: explicitly chosen integer; never infer 3584 from Android brightness
- output: new repository-relative path under `artifacts/`
- emergency_reboot_approved: true
- watchdog_reboot_approved: true
- watchdog_seconds: 600
- camera_profile: `A001_Galaga_OpenCamera_1.56.2_720p_h264_no_audio_100us_iso6400`
- owner_confirmation: actual applicable owner words, never a synthetic fixture
- approved_at_utc: real timezone-aware authorization timestamp, not future

Example invocation syntax (replace placeholders; this is not authorization):

```
python3 06-tools/run_dsi_mode_trial.py --a9-reproduce TARGET_ID CAMERA_ID \
  --experiment-id FRESH_ID --authorization PRIVATE_AUTH_JSON \
  --output "$PWD/artifacts/FRESH_ID" --dbv LIVE_CHOSEN_DBV --offline-check
```

`--offline-check` performs no process/device/network operation and creates no
output. Remove it only after review and live read-only transport/camera checks.
The requested output and `~/.cache/legion-y70-trials/FRESH_ID` must not exist.
An attempted execution reserves the ID; failed runs are not silently resumed.
Raw camera/kernel/UI/error outputs and video stay in that current-user 0700
private directory. Public JSON contains only approval scope, redacted events,
validated capture metadata and outcomes. Existing historical paths are untouched.

## Transport and recovery boundaries

`guarded_adb_socket.py` implements only the existing private Unix ADB server's
smart-socket protocol: shell-v2, identity, sync push/pull and authorized reboot.
It never starts a daemon, uses a default server, changes a network binding or
retries a device command. Preflight checks service, fragmented-safe host version
41, local/USB-host ADB version match, private socket ownership/mode, and binds
both live transport IDs to private serials. Operations select that serial on
their own socket, so transport-ID reuse cannot select the other handset.
A missing tunnel fails closed. Read-only enumeration may wait for recovery.
The new protocol implementation needs read-only live qualification before any
hardware experiment; unit tests are not that qualification.

The target identity, build, slot, kernel, module SHA, panel, root, Enforcing,
stock DC, manual/awake state, A001/Galaga/ROW, Open Camera version, camera profile
and capture metadata are checked. Recording samples must advance within one
session and match a 1280×720 video stream; after pulling, ffprobe additionally
requires exactly one H264 video stream and no audio.

A separately authorized detached device-side 600-second reboot watchdog is
armed and checked before the first table. It never writes DSI into an uncertain
queue. On verified stock return or verified recovery it is disarmed. If arming
fails before a table, cleanup independently disarms it. If host/tunnel loss or
queue uncertainty prevents recovery, leave it armed and preserve evidence.
This bounds a normally scheduling userspace, not a hung kernel, broken reboot
path or power loss. Actual ordinary reboot recovery has to be qualified by the
coordinator. Cleanup after an unverified recovery must not claim restoration.
A dormant sleeper exits later without action after its sentinel was removed.

No live qualification, new capture, device write, commit or push was performed
by this implementation task. A single 100us run is qualitative reproduction,
not proof of ≥2000Hz. A shutter-sweep/hold extension is intentionally not enabled
without its separately implemented and validated capture-control scope.

## ESD write-token correction (2026-11-08)

The target module's ESD-mode write handler compares newline-terminated strings:
`esd_sw_sim_success\n` at `.rodata+0x1a085` (call `.text+0x1b14f4`) and
`reg_read\n` at `.rodata+0xf479` (call `.text+0x1b14e0`). Its read handler returns
the bare mode. Previously the shared short reader wrote tokens without newline;
an accepted bytecount therefore did not establish a mode change.

The shared reader now writes exact newline bytes, verifies simulated-success
readback before any register query, and verifies native reg_read during cleanup.
The runner requires an explicit ESD_ISOLATED marker and records
`esd_isolation_verified: true` only for the corrected sequence. Its restore-only
cleanup uses the same corrected reader. Offline tests cover exact emitted bytes,
read/query ordering and silent-no-op failures for both isolation and restoration.

Historical successful stock/readback/video evidence is not rewritten. In
particular, prior `ESD_RESTORED reg_read` alone proves neither temporary ESD
isolation nor absence of concurrent native ESD polling during those reads. The
corrected sequence requires live revalidation; this code change itself is not
new on-target evidence.

## Optional framed C1 comparison

Add `--capture-c1` to the fresh reproduction invocation, including its
`--offline-check` first. Without this flag, the original authorization schema
and three optical phases remain supported. With it, the fresh authorization
must additionally contain exactly:

```
"c1_capture": {
  "page": 35,
  "opcode": 193,
  "length": 3,
  "stages": ["stock", "a9_only", "stock"],
  "refresh_hz": 120,
  "position": "after_selector_readback_before_hold",
  "framing": "dcs_long3_wc3_ecc_count9_scratch16",
  "read_only": true
}
```

A C1 scope without the flag, a flag without the scope, or a changed scope is
rejected before device access. The chosen `--dbv` is also the C1 state guard.
Every phase runs selector readback, one bounded C1 capture, then optical hold
and the ordinary after-hold selector readback. It does not sweep refresh or DBV.

The existing runner `target()` executes `capture_ddic_c1.reader_script` using
its already-bound target serial. The callable helper that creates a new ADB
binding is deliberately not used. `validate_capture` qualifies three returned
bytes using the exact module's response header, WC3/ECC, normalized count9,
scratch16, read/helper PID and cleanup evidence. The main trace independently
requires exactly three additional standalone page callbacks (pending0,
length11, flags0), three zero callback returns and controller returns
`[0,3,0,0]` for C1 itself. The one qualified background exception is a
`kworker/N:N` return1 from the exact
`dsi_display_validate_status+0x154/0x308 [msm_drm]` callsite strictly outside
the first-through-last C1 page callback window. Such events are recorded
separately as native ESD before the window or resumed after restoration; they
do not enter the C1 return sequence. Wrong callers/tasks, arbitrary additional
returns, negative results or ESD inside the C1 window fail closed. Timestamp
ordering and the complete prior event-line prefix must remain unchanged. The entry counter is
updated from this validated trace, not blindly increased.

The parent mutex now contains a root-owned0600 `owner` file inside its
root-owned0700 directory. Its token combines the fresh experiment ID with a
random suffix. Acquire never overwrites an existing lock. Verify checks root
ownership, modes, regular/non-symlink paths and exact token. The child joins the
held token, leaves it intact, and the parent verifies it again after capture.
Final release verifies the same ownership before removing only that token file
and empty directory; unknown/stale locks are never cleared automatically.
Tokens are redacted in public command events.

Each stage's `c1_capture` report includes qualified data, framing, main-trace
accounting and cleanup outcome. Raw C1 and before/after trace logs remain in the
experiment's private directory. Capture failure follows the existing uncertain
queue/reboot/watchdog path; no recovery DSI table is appended.

This compares A9 status and a possible DC-like one-pulse versus higher-count
behavior. C1 semantics remain unproven and no result is converted to PWM Hz.
The stock driver's malformed-response hazard is unchanged: post-read framing
checks cannot prevent a kernel fault that occurs before a response is returned.
The independent600s watchdog cannot recover a non-scheduling kernel.
