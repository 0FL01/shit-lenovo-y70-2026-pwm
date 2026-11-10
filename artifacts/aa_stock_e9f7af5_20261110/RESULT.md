# Exact full-stock control: e9f7af5, 2026-11-10

## Result

**Failed baseline qualification; operational restoration verified. PWM remains unknown.**

The owner explicitly approved one complete full-stock control with camera after
the prior attempt was rejected before launch. The new attempt used the unchanged
prepared operator/configuration and e9f7af5788c016b6bf60a724498e02ff29987dec.
Before launch, both local one-shot outputs and both remote trial/output directories
were absent. Fresh guarded readiness/preflight at 11:47 UTC verified the target,
camera, root, module, server binding and unchanged boot/transport identities.
The display was already awake and unlocked; no wake or swipe was sent.

The one attempt ran from 11:48:49.559 to 11:50:12.826 UTC (nc-lab clock),
83.267 seconds, and returned SSH rc1 with a completed transport, not a timeout.
There was no automatic repeat. The source and deployment were independently
reviewed; all 32 manifest paths matched. The focused offline source check passed
155 tests with four private-fixture skips, not a full zero-skip suite.

## Executed scope and stopping point

- Only the baseline full stock table was attempted and runtime-validated:
  five chunks/callbacks and all 75 native controller packets matched.
- The recorded mode remained stock OFF at native DBV3600/native 120 Hz for setup.
  These are brightness/refresh markers, not physical PWM frequency.
- The opened Settings observation at 11:49:22.704 UTC was rejected with
  `Foreign Settings observation component`. The completed baseline hold,
  short-watchdog arm, sham and return phases were never reached.
- Candidate dispatch was disabled. There were zero AA10/P85-14 attempts and zero
  unknown-value writes. Inert AA10 chunk files were prepared but never dispatched.
- The observation contains a stopped historical main Settings activity plus the
  resumed timeout chooser. The old component allowlist rejects the historical
  activity before deciding whether the live scene has settled. Offline replay
  additionally found that Looper transaction descriptions were counted as
  support fragments by a whole-activity matcher. The proposed correction scopes
  that matcher to the actual support manager. On the unmodified saved frame,
  the live scene still lacks focus and must remain pending, not stable success.

## Recovery and independent postcheck

The saved acquisition reports one accepted ordinary same-target reboot, a changed
boot with root/module/stock-DC/ESD re-verification, original settings/native DBV828/
logger restoration, stopped camera, trace/chunk/UI cleanup, disarmed overall
watchdog and released research mutex. The short active window never started.

A separate read-only guarded postcheck completed at 11:53:37.131 UTC and confirmed:

- target identity, root UID0, stock module/panel and SELinux Enforcing;
- native brightness828, backlight power0, panelDC0 and logger0;
- Android brightness98/manual, min/peak120.0 and timeout1800000;
- research mutex absent and camera in nonrecording PREVIEW;
- final pinned-server association still valid.

This postcheck made no phone changes. Target transport and boot identity changed
as expected after the verified reboot; camera identity and boot stayed unchanged.
An independent saved-evidence reviewer verified complete response bytes and
current-state comparisons against the original values. These observations corroborate
restoration; they do not independently replay all per-command historical logs.
ESD/watchdog/temporary-resource conclusions additionally rely on the saved
runtime checks. No physical/optical DDIC restoration, exact Hz, comfort or
>=2000 Hz improvement follows from operational markers.

## Evidence and limits

Original run.json, command outcomes, exact calibration/opened observations and
postcheck bytes are retained privately on nc-lab. Device identifiers, raw UI and
camera media are not committed. The source-bound report remains unmodified.
The failed acquisition has no completed optical phases and cannot qualify a
candidate. Its 69,619,739-byte camera recording remains private and unanalysed;
there is no reason to infer a stock optical result from it.

## Reviewed offline correction

The two parser defects are corrected without changing the complete live-scene
parser, its exact digest, the one-second acceptance budget, input ordering,
DSI programs or watchdog/recovery limits. Stopped historical Settings evidence
must belong to its actual native/root/support sections; relocated, missing,
duplicate or contradictory classification fields fail closed. Active fragment
identity checks use only the support manager's fragment section.

Final scoped verification: 189 runtime/source tests in each of normal and
optimized Python, with four unavailable historical private-reference skips per
mode; 84 consumer tests per mode without skips. Exact current-run private replay
passes both modes using independent calibration captures, not a reconstructed
expected scene. The unchanged raw frame remains pending; the real caller with
fake I/O times out under the original budget, one open and no Back.

Independent revision2 review passed 85 tests per mode with three historical
fixture skips, both original relocation failure reproducers, 28 additional
negative combinations and exact current-run replay. See the
[correction review](../../06-tools/aa_timed_runtime_20261109/historical_settings_20261110/REVIEW.md).

This is an offline source correction, not new physical evidence. Deployment
remains e9f7af5. Any new physical qualification must be a separately assigned
fresh run; the consumed one-shot output is never reused. No PR, protected-branch
merge, flash or candidate operation was performed.
