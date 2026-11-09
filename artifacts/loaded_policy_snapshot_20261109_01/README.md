# Loaded policy snapshot: offline acquisition preparation

Not executed. Lead alone may execute after independent review and separate offline
libsepol CN harness qualification. This artifact does not modify the previously
executed fixed-receipt source or its retained spent device BASE.

Default/--check verifies source pins only, creates no files and constructs no
transport. --execute is the sole explicit live option. It requires fresh public
result/private cache paths and uses umask077, private directory0700 and files0600.
The guarded transport source hash and acquisition source hash enter public result.
Exact commands, complete/partial streams and per-call events remain private;
public result exposes counts, hashes, context and guard booleans, no boot/serials.

The fixed read-only device sequence uses existing-server/version guards, fresh
immutable target/camera bindings and identity checks; camera is read only for
identity. Target build/slot/kernel/panel/module/root UID/shell UID, boot, Enforcing
and absent research mutex are checked. No test-w, producer, capture/seal, device
file writes, chmod/chown/chcon, audit changes, settings changes, reboot or alternate
location exists. No retry of a failed/denied operation exists.

Reads fresh plain-shell /proc/$$/attr/current (the command-owning shell PID,
not the cat child) and root /sys/fs/selinux/policy.
Stat size is checked first. A zero selinuxfs size is non-meaningful metadata, not
proof of an empty policy. The actual read must be nonempty and at most16MiB;
positive advertised size must match. Shell-v2 caps bytes before payload reads and
requires a completed exit frame, rc0 and empty stderr. Policy read has a30-second
host acceptance deadline, not cancellation. Uncertainty retains private partial
complete frames and HOLD, without retry. A separate root SHA256 must match the
private snapshot; final size, boot/mutex/Enforcing are checked.

Header checks reject unsupported magic/identifier/version and truncated header,
but are NOT complete structural validation. Result remains
SNAPSHOT_CAPTURED_PENDING_OFFLINE_PARSE, with full_policy_parser_validation=false.
Do not call this a valid parsed policy until the separately qualified offline
parser consumes these exact hashed bytes. A truncated policy body is not excluded
by header checks alone. No live plan is admitted until that qualification exists.

The public context describes a newly observed plain-shell process, not the earlier
terminated failing shell. Same boot and matching policy hash observations do not
prove absence of intervening runtime policy changes. Installed CIL is not assumed
to equal loaded binary policy. A loaded snapshot is not security-setting alteration.

Focused fake tests only, no ADB/device/filesystem writes:
PYTHONDONTWRITEBYTECODE=1 python3 -B test_acquire.py
PYTHONDONTWRITEBYTECODE=1 python3 -O -B test_acquire.py

Acquisition and later offline query remain separate; this script never loads or
runs libsepol. Lead may separately use the reviewed query_saved_selinux_policy.py
after its qualification. No query result or readiness is implied by capture.

## Context ABI and owning shell

The fixed command is `cat /proc/$$/attr/current; rc=$?; exit "$rc"`.
The status-preserving continuation keeps the command-owning shell alive instead
of permitting a final-command exec optimization to replace it with cat.
Exact binary context bytes are retained privately. Parsing requires precisely one
terminal NUL and an otherwise strict ASCII context; LF, CR, absent terminator,
embedded/multiple NUL and ambiguous combined terminators are rejected, not trimmed.
Only the decoded context is public, never PID.

Saved kernel evidence under sources/gki-15950084/common:
- security/selinux/hooks.c:6362-6420 (`selinux_lsm_getattr`) selects the task SID,
  calls security_sid_to_context and returns its full len; :6601-6614 delegates.
- security/selinux/ss/services.c:1218-1265 computes context storage including NUL
  (three name lengths plus three bytes, with two colons and one terminal NUL),
  appends MLS representation, and explicitly sets *scontextp=0.
- fs/proc/base.c:2790-2810 passes that full length to simple_read_from_buffer.
This establishes the expected saved-kernel ABI, not a new live observation.

Private partial files are retained on uncertainty. No universal cleanup or remote
cancellation proof is claimed; no device mutations are planned.
