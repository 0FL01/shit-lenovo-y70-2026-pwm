# Stock base-rate control — 2026-11-07

R3 remains active; this is a causal timebase test, not a >=2000Hz profile.
Scope: owner-authorized autonomous optical work and latest HORIZON continuation.
Only normal Android refresh controls and the previously verified standard DBV
setter are used; no raw DDIC replay, read-page selector, new DSI bytes, ESD
disable, flash, reboot or persistent PWM settings.

## Question and prediction

`hypothesis`: fine optical structure is tied to the native base timing family.
Live tables use page2D:83 for120-based divided modes (120/60/30/24 and idle),
page2D:84 for144, and page2D:85 for90. Thus the completed120/30 test did not
necessarily change the base. The earlier trial named `mode90` changed23:80 to
hex90; it was not a90Hz refresh trial. Existing144Hz register-dump metadata
contains no simultaneous optical video or stable-return controls.

One sequence: **120 →144 →120 →90 →120**, DC OFF, native DBV3600 throughout,
same Settings field, guaranteed chooser-open/cancel redraw before each hold.
Camera stays100us/ISO6400/AE-AF OFF/focus9.11752701/EIS-OIS OFF. Each hold7s;
only central windows are analysed with spatial-v2 (no temporal demeaning).

Reversible changes in spatial periods/phase at144 and90 would distinguish
base-sensitive image structure from unchanged structure. **Do not interpret
pixel-period ratios as physical-Hz ratios**: panel scanning contributes spatial
phase, sensor/output mapping remains uncalibrated, and harmonics may change.
Native timing payload/order, same DBV and nonnegative controller returns must
be verified, not inferred from UI refresh metadata. Any result changes the next
hypothesis; none alone establishes the final PWM goal.

## Gates, rollback, evidence

Re-identify both transports; verify XT2611-1/build/kernel/selected panel/root,
Enforcing, DC0/logger0 and prepared Pacman metadata. Use only a fresh output;
do not rerun a completed sequence unchanged. Abort on identity, camera, mode,
brightness, native-error or trace-loss mismatch. Preserve any partial evidence.
Capture initial target settings and native DBV. Finally stop only our recording,
disable/remove our probes and logger, restore exact captured manual/native DBV
and refresh policy, verify DC0/Enforcing. Keep Pacman prepared/awake as requested.
The earlier pre-investigation automatic policy is still due at final session
cleanup, not silently treated as this trial's initial state.

Implementation: `06-tools/capture_ui_dc_reference.py --base-rates` after the two
explicit transport arguments. New run/video/private logs have separate paths.
Live base-rate controls are not a repeat of the consumed A9/9D authorization.
