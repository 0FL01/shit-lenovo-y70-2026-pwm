# Android validator portability: offline review bundle

**Status: HOST-ONLY development, independent review pending. Never run on either
phone from this deliverable.** This is a fixed synthetic userspace capability
suite, not a sequencer, runtime adapter, physical trial, or admission mechanism.
There is no DSI command, ADB interface, camera operation, setting change, mount,
SELinux change, install, reboot, arbitrary command argument or P85=14 fixture.
The only allowed P85 payload fixture is factory [21,0,0]; C1 is [0,0,96].

## Files and reproducibility

- `build.py`: stdlib-only generator. Refuses an existing bundle rather than
  silently changing a review snapshot. Copies exact offline sources, generates
  synthetic bytes and the fixed command list. Never imports a trial runner or
  reads the private corpus.
- `bundle/probe.sh`: exact shell under host test; two arguments only: new absolute
  owned work-directory path and expected UID. It discovers its bundle from its
  own absolute path. No generated phone file needs Python.
- `manifest.json`: pins copied source Git blobs and SHA256 of every generated
  executable, fixture and case specification. `SHA256SUMS` is checked before work
  creation. The trusted host manifest must also be checked independently: a
  self-consistent rewritten SHA256SUMS is not authentication.
- `test_host.py`: executes this generated shell only on nc-lab. Required checks
  are explicit exceptions, not Python bare assertions. Run with Python normal
  and `-O`; results and exact invocation rc/stdout/stderr bytes (hex) are retained
  separately. Each fixture operation has its own three capture files. Internals
  of frozen validators retain their existing per-tool checks; this probe does
  not claim to intercept every internal subprocess.
- `results-{normal,optimized}.json`, `observations-*.json`: host evidence only.
  Inputs and outputs contain synthetic data, no saved phone evidence.

Build once after source freeze, then execute:
`python3 06-tools/android_validator_portability/test_host.py` and
`python3 -O 06-tools/android_validator_portability/test_host.py`.

Source mismatch, manifest mismatch, launch collision, valid output followed by
nonzero status/LF/NUL diagnostics, cleanup refusal and cleanup diagnostics are
tested. Host-only stubs live in fresh private PATH directories and never replace
system utilities. A foreign sentinel must remain byte-identical. Existing launch
directories are not adopted. Existing qualified runtime and offline validators
are never edited by these files; test verifies all thirteen qualified runtime
blobs.

## Future launch contract: NOT permission or an implemented launcher

1. Lead exclusively controls physical access. Preserve exact ADB service/version
   preflight, current target/camera identity separation, exclusive access and
   existing mutex ownership policy. Never guess serial, transport, private
   address or Android temporary parent. No device command is provided here.
2. Review frozen snapshot and dependencies, then choose explicit trusted absolute
   temporary parent and selected shell/PATH. Copy only reviewed generated bundle,
   verify trusted manifest and permissions/ownership. Each execution context
   requires its own newly owned 0700 directory and 0600 fixture files. Current
   UID must match the separately approved context: UID2000 versus UID0.
   No `su` appears in this suite. Never execute old runtime envelopes as root.
   The envelope **decoder** here merely reads synthetic files.
3. Required existing commands: sh, timeout, sleep, id, sha256sum, mkdir, rm,
   rmdir, cat, cmp, tr, od, tail, wc, stat, awk, mv. Missing commands abort before
   workspace creation. No installation/fix is attempted. Shell, PATH authenticity
   and stable exclusively owned parents remain external prerequisites.
4. The plan proposes a 10-second entire-batch deadline; it is **not yet qualified
   or implemented as a remote cancellation protocol**. Before any future launch,
   review a target-local outer timeout and process identity/reconciliation
   contract. Host test has a 60-second caller timeout, which is not remote
   cancellation. Existing per-case timeout is 4 seconds plus 1-second kill grace;
   only its own finite 2-second sleep exercises timeout behavior. No endless
   writer or child trial is created. Timeout/137 aborts further dispatch and
   omits OBSERVED; inability to prove termination keeps result unknown.
5. At most one fixture invocation runs at once. Fixed command graph has at most
   eight concurrent processes (conservative allowance for supervisor/subshell, outer case timeout, case shell, nested
   utility timeout, utility shell, own sleep). Finite input bytes and command
   count are in manifest. No source downloads or free-form commands exist.
6. Initial fixtures are below 1 MiB total. A finite <=2048-byte child observes
   `ulimit -f 1`; host oracle accepts only observed sizes512 or1024 with a
   nonzero producer status. No unit assumption is used as qualification.
   Per-case subshell sets `ulimit -f 32768`, preserving the unchanged interval
   wrapper contract; only after unit observation would that imply <=32 MiB
   per-file process ceiling on that shell. A smaller hard ceiling was tested
   and correctly rejected because interval cannot raise it. Unexpected units fail host review.
   1 MiB/file and 16 MiB total are review/output caps, checked on host; total is
   **not a remote disk quota**. Maximum fixture expansion is tiny here, not the
   offline validators' full admitted caps. A storage-bound launch contract
   remains necessary before any Android execution. Manifest worst-case serial
   timeout sum is accounting, not permission to run for that duration.
7. Outputs intentionally remain in the new owned work directory for retrieval.
   OBSERVED means only that the fixed command list ended, even if expected or
   unexpected feature tests failed. It is **never a PASS/success receipt**.
   Only independent byte/status review can report prerequisites observed.
   Wrappers clean their own fixed scratch names. No shell recursive cleanup,
   wildcard deletion or automatic reboot exists. Own remnants after cleanup
   failure remain quarantined. They are userspace cleanup uncertainty, **not**
   DSI target uncertainty, because this suite cannot dispatch DSI.
8. Future caller must retrieve results and separately account for fixed owned
   files, directories and termination before deletion. This bundle intentionally
   does not implement a device cleanup API. Host TemporaryDirectory cleanup is
   limited to fresh synthetic test instances and does not establish device cleanup.

## Coverage and explicit non-claims

Exercises real generated shell operations, byte-preserving tr/cmp/od/tail/wc,
empty/no-LF/LF/NUL/non-ASCII data, 32768/32769-byte fixture lines, metadata,
noclobber collision/override, inherited FD8 after unlink and empty/LF/NUL audit
decisions, AWK arrays/delete/split/sub/match/RLENGTH/ENVIRON and microsecond numeric
precision. Whole frozen capture (write/85/C1), interval, envelope and snapshot
wrappers execute with known synthetic valid/rejected cases. Full envelope byte
1..127 decoding also exercises AWK getline/close/%c/ARGV dependencies.

This is a small portability smoke, not exhaustive semantic requalification:
STATE_ONLY does not prove owner execution or supply ESD. Separate state.awk
raw-ENVIRON tests use an explicitly synthetic ESD fixture only; it is never
acquisition evidence. Literal backslashes, alias rejection and missing identity
exercise the corrected mandatory raw P85_OFFLINE_EXPECTED_BOOT API. Nearby numeric
boundaries are sampled, not floating-point equivalence proof. Current wrapper
limitations remain inherited, including snapshot bootstrap/final-cleanup
NUL-free diagnostic assumptions. Read existing component READMEs.

A manifest does not establish root sealing, same-UID race resistance, immutable
acquisition, durable epoch ledger, power-loss/crash ordering, clock origin/rate or
suspend behavior. Host timing cannot establish Android max-cap costs or a future
successful-return bound. All successful-path bounds remain UNKNOWN. Preserve
37/45/8, SHORT60 and OVERALL600; none of those budgets is proved by or changed
for this probe. Physical runtime remains source1785d32 and its13 blobs. P85=14
stays unavailable and no physical PWM result follows from this work.

