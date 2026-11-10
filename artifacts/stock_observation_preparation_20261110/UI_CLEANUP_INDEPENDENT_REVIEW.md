# Independent camera UI cleanup correction review

Final offline code verdict: PASS for FREEZE_UI_CLEANUP.json, superseding the
withdrawn13e6 coordinator review. No devices, ADB/research-usb, deployment,
commit/push or private configuration/receipt inspection occurred.

Coordinator SHA256:
`4aafb89a3bb8396476b0a26edba337b6687cabc07a4883b88a722fbaace5a8e8`.
All24 freeze entries independently match. Independently reran aggregate unittest
discovery with PYTHONDONTWRITEBYTECODE=1:68 PASS normal and68 PASS python3 -O.

## Correction checked against actual coordinator methods

- Each settings/navigation input latches ui_restore_pending and transition
  intent before dispatch. Input exceptions retain sticky uncertainty. A later
  observed screen cannot silently clear uncertain input outcome or trigger retry.
- Command-returned transitions clear only after the expected observed level or
  exact filesize-switch value. A read interruption can later be resolved by a
  new read of that known expected destination; this is not input replay.
- Cleanup runs independently of preference-value changes. Recognized preview,
  main settings, video settings and exact option dialog use explicit known
  navigation edges. Unknown UI or uncertain transitions receive no Back/Settings
  input and retain cleanup_pending/ownership.
- Fresh original preview critical-control signature and strict metadata are
  captured before mutex acquisition. Cleanup verifies the same controls/layout,
  required manual profile and no encoder stream. Restore, release and capsule
  additionally reject pending or uncertain UI state. Recording Start separately
  invalidates the UI-restored claim before dispatch.
- An initial failure with owned UI scratch also records pending cleanup rather
  than treating absence of changed preferences as complete restoration.

Seven added regressions exercise real navigation methods with synthetic XML:
enter-after-Settings-tap timeout; leave timeout with all preferences unchanged;
known dialog/read interruption and supported cleanup edge; uncertain Back with
no further input; normal changed-preference/UI rollback; unknown UI; unknown
dialog classification. The two previously reproduced false-cleanup paths now
retain ownership and never call restore/release. Normal rollback returns to
verified original preview and restores actual captured preference values.

Existing construction/source binding, encoder-stop guard, v2 receipt intake,
single Start/no Stop, custody and capsule tests remain passing. No production
preload guard or scientific threshold was weakened. Stat comparisons still use
explicit relevant fields excluding atime.

## Limits

UI tests are synthetic, not evidence that the actual installed UI matches these
supported shapes. Signature covers the relevant Start/Settings controls and
metadata, not every preview pixel. Effective duration/current MAIN intent,
fresh geometry, source deployment and execution permissions remain separate
unfulfilled runtime prerequisites. Unknown actual layouts fail closed without
blind navigation. This review restores code-level PASS only, not live admission.
