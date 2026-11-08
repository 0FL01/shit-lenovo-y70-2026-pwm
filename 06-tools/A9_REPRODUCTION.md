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
