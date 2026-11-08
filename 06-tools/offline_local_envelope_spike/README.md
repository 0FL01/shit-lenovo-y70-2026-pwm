# Offline byte-envelope feasibility spike

**Not a controller, acquisition mechanism, trusted provenance check, or execution gate.**
There is no device/ADB/DSI/transport call, child runner, integration or live CLI here.
No next child may execute based on this component. Physical PWM >=2000 Hz is still
unproven; unknown P85=14 stays disabled. Existing 37/45/8 and independent 60-second
watchdog behavior is unchanged. A host timeout is not remote cancellation. Future
execution uncertainty requires reboot-only recovery, never blind15/page0/retry.

## Files-only interface

Invoke `sh /absolute/path/decode.sh RAW PLAN NONCE PRODUCER_RC PRODUCER_STDERR OUTPUT`.
All file/directory arguments must be absolute. OUTPUT and OUTPUT.stage must not exist.
PLAN is a **trusted expected plan**, not obtained from the submitted envelope:
1–16 lines of `LABEL CAP` with unique `[A-Z][A-Z0-9_]{0,39}` labels and canonical
integer byte caps 0..16777216. Plan length is bounded to 976 bytes. NONCE is the
trusted expected 12 lowercase hex characters. PRODUCER_RC must be exactly `0`;
PRODUCER_STDERR must exist and be empty. The caller supplies actual acquisition rc
and stderr, not fabricated defaults. Files must be stable, regular, readable and
not symlinks. File arguments carry no claimed provenance by themselves.

Success requires exit 0 and OUTPUT/SUCCESS containing exactly
`P85-OFFLINE-ASCII-ENVELOPE-v1` plus LF. OUTPUT contains only that marker and
section01..sectionNN, in trusted plan order. Each section file preserves exact
payload bytes, including absent/present final LF, controls and empty payloads.
No evidence-provided label is used as a path. Labels from the validated plan are
used only for matching; output basenames are fixed numeric ordinals. Do not treat
staging files or sections without a successful invocation and SUCCESS as valid.
No downstream execution is part of this API.

The wrapper checks total raw size <=25165824 before `od -An -v -tu1`, materializes
the byte stream to an owned staging file, and verifies the total od-token byte count equals the independently measured raw size,
then checks each wc/od/awk producer rc and
stderr separately. There are no evidence shell variables, command substitutions,
pipelines, Unicode character counts, or executing input. AWK receives decimal byte
tokens under LC_ALL=C, maintains bounded 160-byte framing lines and a 4096-byte
payload output buffer, and checks framing across chunk/line boundaries. Its only
payload retention beyond the buffer is the rolling nonce prefix. Successful close
of each section is checked. A payload directory is renamed into place only after strict DONE and no trailing
byte. SUCCESS is written only after rename reports success. Ordinary failures clean only the explicitly owned
fixed files and directory, never wildcard/rm-rf paths. If cleanup itself fails,
return is nonzero and any residual staging directory must be quarantined externally.
Publication uncertainty is also possible: rename may complete before its tool returns
an error, leaving section files but no SUCCESS. An interruption after the subsequent
SUCCESS write is also possible. A final directory/SUCCESS alone is never authority;
nonzero/unknown invocation result invalidates it and requires quarantine.
The decoder deliberately does not blindly delete a final path after uncertain rename.

## Relation to the exact Python oracle

Reference: `p85_batched_envelope.parse()` and timed caller
the `envelope()` method in `run_p85_timed_stock_trial.py`.
Pinned parser blob: ac3d55f5f7928ad8e55b9090615e23f9f35d5e0e.
Pinned timed-caller blob: 9c804b7f12c5a77768d2487c31703b66c540f62c.
Checkout at implementation: 3bf33d60a33af3657bf278e00252f797a4d2c182.
Qualified runtime source commit: 1785d32fd011314df3f1c5c55a5d3cbe0ee6b8a2.

Common semantics: exact nonce START; exact expected ordered sections; zero rc and
stderr; byte length <= trusted section cap; exact payload boundary LF and matching
END; forbidden nonce-prefix anywhere in payload; forbidden NUL; required DONE LF;
no missing, duplicate, reordered, nested or trailing framing accepted. A delimiter
for a **different** nonce within payload is allowed, just as in the oracle.

Explicit narrower dialect: all input bytes must be 1..127 (ASCII, including controls
and DEL). Non-ASCII, even valid UTF-8 accepted by Python, is rejected. Header rc and
stderr lengths must be literal 0 and payload lengths canonical decimal, whereas
Python accepts leading zeros within its 3/9/5 digit widths. Trusted plan caps are
also canonical. These are deliberate stricter rejections, not full equivalence.
Plan command/root/seconds/owner binding are not ported: they are trusted acquisition
and execution-plan obligations, and this component cannot establish them. The test
oracle uses inert commands solely to satisfy Python metadata validation.

The timed caller also checks post-child KERNEL marker count and native activity
and applies later semantic checks. Those checks are **not** envelope framing and
are not implemented here. Source/owner/freshness acquisition, capture/state/factory
values, camera, intervals, deadline and recovery each require independent integration.

## Offline tests

Run `PYTHONDONTWRITEBYTECODE=1 python3 06-tools/offline_local_envelope_spike/test_decoder.py`
from the repository. This synthetic suite requires no private corpus or added
package. Add `--private` only on the research host to include all 84 saved complete
envelopes from the three recorded runs. Trusted expected nonces come from manifest
records and plans from recorded event labels mapped independently to pinned plan
semantics, never guessed from mutated input. Every accepted case, including every
mutation, is compared against the exact Python oracle and section bytes. Test scratch lives only in an atomic 0700 /tmp/pwm-envelope-test-* directory,
with 0600 evidence files and exact per-instance cleanup. Explicit runtime guards remain
active under Python -O. Logs contain
sanitized counts and pinned source IDs, never payload dumps. Corpus mutation handling
and Python extraction are test helpers, not proposed runtime implementations.

Coverage includes every byte truncation of a representative envelope (therefore all
framing boundaries and payload offsets), private truncations and trailing data,
incorrect/negative/overflow/leading-zero lengths, nonce/header/footer faults, label
path injection, delimiter/nested/same-line payloads, rc/stderr, NUL/nonASCII/controls,
random insert/delete/replace mutations, section caps, oversized input, empty/malformed
nonce and trusted plan, and wc/od/awk valid-output-plus-exit/stderr faults. Ordinary pre-publication failure cases check absent final output and cleanup. An
injected rename-that-completes-then-reports-failure case checks nonzero exit and
requires the remaining directory to have NO SUCCESS marker and classifies its section
files as uncertain, never as valid output. Finite corpus tests do not prove
a universal subset, portability to Android, timing fitness, or live safety.

## External requirements and limitations

Trusted shell/tools/PATH/script files and exclusive, trusted output parent are required.
Shared-UID adversarial TOCTOU, concurrent input changes, source ownership/provenance,
freshness, producer authenticity, signal/KILL/power-loss durability, filesystem quota,
and atomic publication under an attacker are **not solved**. No shared-UID security
claim is made. The shell can verify a supplied rc/stderr, not that it belongs to the
supplied bytes. rc/stderr fault tests are failure propagation tests, not proof against
malicious replacement tools. POSIX sh/awk/od are intended; only installed host tools
are tested. `od` has bounded but substantial disk expansion (~4.25x input); temporary
storage provisioning is a separate future constraint. There is no timeout claim.

Host feasibility timings in results measure only each complete valid corpus decoder
subprocess (shell/od/AWK/files), excluding oracle and fixture setup. They are descriptive
host min/median/max, not Android performance or a bound for any active deadline.
