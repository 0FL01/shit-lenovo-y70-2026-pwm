# Independent diagnostic v2 review

Final verdict: PASS for read-only diagnostic delta, not capture admission.
Helper SHA256 `6429d7f3d7d4e15b603c63ba55ee9437d7797214ca6dd3695e4990dda8832791`.
All four current PRESTART_V2_FREEZE.json hashes independently matched.
Original v1 remains `5af512cf02640e0813e627d9967439bcc1ed5ef334485f1d53cb73000158c723`.
Independently reran50 aggregate tests in normal Python and -O: PASS both.

Delta retains exact device commands, source construction and pure parser guards.
It creates only a distinct fresh prestart-inspection-v2 evidence child, adds a
fixed numeric stage/reason taxonomy and bounded shell return/byte counts, and
may create exclusive private failure.json. No raw values, exception messages,
commands, identifiers or camera tokens are exposed by failure diagnostics.
No retries, setup, recording, repair, source guard weakening or alternate server.
Baseline exceptions may be reduced to generic rejection by the original observer;
reason1 is not itself a causal diagnosis.

The initially frozen69af helper had a reproduced bug: a final close failure was
followed by a no-op second close and falsely marked cleanup verified. Final code
keeps stage91 cleanup uncertainty sticky and does not call close again. Added
regression asserts stage91/reason3, cleanup=false and exactly one close call,
while retaining the provisional existing receipt. This resolves the finding.

Source-only remains inert; a subsequent separately admitted read-only attempt
must use the fresh v2 child and not resume/adopt v1 evidence. Completion and
uncertainty still use final stdout plus process/SSH exit, never provisional disk
receipt alone. This diagnostic revision establishes no root cause of the prior
failure and no current-device fact until actual execution succeeds.

Offline review used public repository and synthetic tests only, without devices,
ADB/research-usb, private configuration or denied receipts. Actual camera launch
intent can override saved duration; native10s effective limit must not be inferred
from UI preference alone. That remains separate capture-path evidence.
