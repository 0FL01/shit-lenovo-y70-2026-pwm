# Independent prestart inspection review

2026-11-10, public repository review only. Result: PASS for the narrow read-only
inspection helper. No device, ADB, research-usb, deployment or private receipt
access occurred in this review.

Reviewed helper SHA256:
`5af512cf02640e0813e627d9967439bcc1ed5ef334485f1d53cb73000158c723`.
Reviewed test SHA256:
`bf2c7696ad70e11b4a27c749a83e06ecfbed760f125659bccf22a62d1bd393f1`.
All six PRESTART_FREEZE.json entries match actual bytes. Existing launch.py,
probe.py and deploy_readonly.py remain unchanged. Independently reran all40
tests in normal Python and python3 -O with PYTHONDONTWRITEBYTECODE=1: PASS both.
These include11 prestart tests, fake transport, real pinned pure parsers and
concrete construction with fake Git and socket creation forbidden.

## Verified scope

- Actual OfflineBaselineADB.shell(alias, fixed_command, timeout) returns binary
  stdout for screencap -p; no unsupported exec-out API or on-phone file write.
- Fixed command/role allowlist; no touch/keyevent, settings, recording, DSI/ESD,
  mutex acquisition, recovery, reboot, daemon start or alternate transport.
- Exact launch/probe hashes, configured d5 commit and tracked dependency bytes;
  native_state/software_hz are extracted from independently pinned public source
  as pure AST functions with matching globals and real signatures. No Trial import.
- Source-only mode performs inert construction, no proc/socket/device/evidence
  action. Actual inspection requires --execute-read-only.
- Refreshed baseline, same immutable role transport, before/after boots, repeated
  native/software/scene observations, two same-session advancing PREVIEW snapshots.
- Fresh private prestart-inspection child under pinned0700 evidence parent;
  exclusive0600 images/receipt with inode, size, link, mode and hash checks.
  Collision fails, partial evidence retained; no overwrite, repair or removal.
- No raw dumps/image bytes/serial/boot/session identifiers in stdout. Private
  receipt contains role association and screenshot custody. Static failure output.
  On-disk receipt is provisional; success is final stdout with cleanup true and
  successful process/SSH outcome. No retry on uncertain outcome.

No blocking code finding for the parent's proposed minimal deployment: verify
host/code/observer identities, authenticate this helper before running it, create
its file exclusively without overwriting existing files, validate existing typed
config against independently prepared values, then run source-only and read-only
in separate fresh isolated processes. Source-only does not spend the evidence
child. This statement does not review private payload contents or claim actual
host compatibility from synthetic tests.

## Interpretation limits

Settings foreground means package-level classification, not exact
DisplaySettingsActivity/hierarchy. Native mode is the latest retained anchor,
not continuous hardware-state proof. Equal endpoint observations do not exclude
an intervening change. Preview geometry/PNG is not encoded recording geometry.
PNG framing/CRC checks are not full pixel decoding or visual ROI review. The
new images must be privately reviewed; capture_admitted and
recording_geometry_qualified remain false. Embedded pure APIs preserve these
limits and cannot turn booleans into a complete capture receipt.

Trusted same-UID/root/kernel/interpreter and no concurrent namespace mutation
remain assumptions. No hard syscall cancellation, malicious-root race defense,
durability, physical PWM or camera-duration claim. Actual recording/setup and
dispatch freshness require the separately reviewed coordinator path.
