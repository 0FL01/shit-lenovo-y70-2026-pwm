# Supplemental read-only prestart inspection

New public helper `prestart_inspection.py`; original launch/probe/deploy freezes
are unchanged. This helper was implemented and tested offline only. It performs
no setup, key/touch event, recording command, device file write, preference dump,
DSI/ESD selector, ownership acquisition, watchdog, restoration or reboot.

The supported binary operation is the existing real transport signature
`OfflineBaselineADB.shell(transport_alias, 'screencap -p', 15) -> (rc, bytes, err)`.
There is no separate exec-out adapter API. The same binary shell signature is
already used in `run_p85_guarded_trial.py` for camera review screenshots.
Screencap emits PNG to stdout; it does not create a screenshot file on the phone.

## Standalone construction and invocation

Externally authenticate this helper BEFORE execution. Required options:

    python3 -I -B /approved/prestart_inspection.py \
      --source-root /approved/frozen/dependency-root \
      --readonly-launch /approved/frozen/launch.py \
      --readonly-probe /approved/frozen/probe.py \
      --private-config /approved/private/config.json \
      --helper-sha256 EXTERNALLY_APPROVED_HELPER_SHA256

Without `--execute-read-only`, source validation and actual inert transport
construction only: no socket, proc scan, device request, directory or file write.
The helper verifies original launch/probe SHA256, configured d5a522ce dependency
commit and tracked bytes, the three exact existing transport/parser dependencies,
and fixed dsi_trial_transaction/stock_c1_sweep sources. Only exact `native_state`
and `software_hz` AST function nodes execute from the latter two files, with
reviewed re/check globals. No Trial or source-file main/lifecycle is imported.
The helper's own checked hash records provenance, but does not replace the
operator's independent pre-execution authentication.

`prepare(source_root, launch_path, probe_path, config_path, helper_sha)` returns
kwargs for `inspect(**prepared)`. Construction uses the actual VerifiedPin,
ProcessIdentity, ProcLimits, LinuxAssociation.acquire_process, fixed socket factory
and OfflineBaselineADB constructor signatures. It does not access private adapter
fields, fall back to ADB CLI, adopt observed server pins or reuse old transport IDs.

Execution creates only the fresh child `prestart-inspection` under the existing
independently pinned 0700 evidence directory in the operator-supplied config.
That child must not exist. Existing readiness.json and all frozen files remain
unchanged. Final child files are exclusive 0600 `target.png`, `camera.png`, and
`inspection.json`; partial files remain on failure. No overwrite/repair/delete.
Held-dirfd identity, owner/mode, namespace edges, file inode/link/size checks and
SHA256 custody apply. Trusted same-UID/root/kernel and no concurrent namespace
mutation remain assumptions. There is no durability or hard OS cancellation claim.

## Read sequence and output

An ordinary original read-only Observation first refreshes identity/root/module/
panel/Enforcing/settings/power/mutex/camera facts using the same constructed
adapter. Its private receipt is retained in memory, not printed or written over
the original readiness file. Supplemental reads then take:

1. Both role boot IDs, matching the refreshed baseline.
2. Latest retained native mode anchor from root dmesg, software display mode,
   resumed/focused package classification, and lock status.
3. Camera PREVIEW metadata, target/camera raw screenshots, then advancing PREVIEW
   metadata from the same session/profile.
4. Repeated target mode/scene/lock observations, matching boots and serial bindings.

Only fixed commands are available. On malformed/unavailable native anchor,
unsupported camera metadata, changed boot/profile/mode/scene, no advancing preview,
invalid PNG, failed association or transport, the operation fails without retry.
PNG framing, CRC, 16MiB cap, bounded dimensions and supported IHDR are checked.
This is not a full image decoder; pixels still require private visual review.

Sanitized output has UTC begin/end; target native/software mode and scene flags;
refreshed baseline; actual manual camera profile including crop and preview stream
dimensions; screenshot labels/dimensions/byte counts/hashes. It contains no serial,
boot ID, session token, raw dumps or image bytes. The private inspection.json adds
actual role/boot association, exact source provenance and PNG device/inode/mode/
owner/size/hash custody. On-disk receipt is explicitly `before_descriptor_close`.
Successful returned stdout is `receipt_phase:final, host_cleanup_verified:true`.

Settings package foreground/focus is **not** proof of an exact Settings subactivity
or visible scene. An unfamiliar lock layout remains null, never unlocked=true.
Native mode is the latest retained dsi_display_set_mode anchor, not a fresh mode
transition or physical PWM evidence. Preview crops/streams/screenshots do not
qualify final encoded 720p recording geometry. Visual review of both new private
PNGs and final video ROI remains separate. `visual_review_required:true`,
`recording_geometry_qualified:false`, `capture_admitted:false`, `pwm_hz:null`.

## Narrow coordinator embedding

To avoid rerunning the whole baseline or constructing another transport during
capture setup, a separately source-bound coordinator can reuse these pure APIs:

- `extracted_parser(raw_source_bytes, name, expected_sha256)` for the exact two
  source entries in `PARSER_SOURCES`.
- `validate_native_scene(native_log, display, activity, focus, lock, *, parsers)`
  returns native_mode/software_hz/settings_foreground/unlocked observations.
- `validate_png(raw_png_bytes)` returns width/height/bytes/sha256.
- `preview(camera_parser_module, raw_metadata_text, previous=None)` validates a
  manual PREVIEW snapshot and optional same-session progress. Returned internal
  parser snapshot includes private session material and MUST NOT be printed.

The coordinator uses its own SAME pinned adapter with the fixed COMMANDS values
and its fresh held private evidence sink, not a caller-supplied ready boolean.
It must independently enforce its exact known Settings scene and capture gates.
No embedded API grants capture admission. A previously reviewed camera PNG alone
does not establish current geometry; immediately retained fresh PNG/controls and
later encoded-video ROI review are separate evidence.

Tests use fake transport I/O, real pinned pure parsers and synthetic valid PNGs.
The concrete construction test uses fake Git responses for the known reviewed
source bytes and forbids socket creation; it never runs the source-only/live
helper against the USB host. No private config/payload/old denied file was read.
