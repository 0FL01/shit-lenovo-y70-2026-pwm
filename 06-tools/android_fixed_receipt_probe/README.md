# Fixed binary receipt probe: OFFLINE proposal

This is one concrete three-phase shell proposal, not a controller, Android runner,
DSI experiment, generic command API, resume facility or live authorization.
The only fixed experimental producer is `producer.sh`; templates also invoke
ordinary filesystem and metadata utility children. It emits stdout `0a00`, stderr
`646961676e6f737469630a00`, then exits **7**. A structurally valid receipt therefore
means EXPECTED_NEGATIVE, never producer success or an admission gate.

## Fixed protocol and trust boundary

Parent host owns preflight, transport, rendering and all actual Android calls.
Render the three templates once, with reviewed literal values, then pin the exact
rendered bytes before use. `common.sh.in` prefixes all three phases. No device
rendering, input-driven source, arbitrary command, status-file adoption or relaunch.
The only seal argument is the actual exit status retained by the trusted host from
its completed synchronous plain-shell capture. Unknown transport status, reconnect,
or uncertain producer completion means HOLD: do not invoke seal or capture again.
A return code supplied by an untrusted producer is not authoritative.

Prospective Android literals (NOT yet qualified):
- ROOT_UID=0, SHELL_UID=2000, SH=/system/bin/sh. Production templates fix
  PATH=/system/bin and LC_ALL=C, never inheriting ADB/KernelSU utility resolution.
- PARENT=/data/local, PARENT_MODE=751, BASE=/data/local/afr_synthetic_fixed_20261108_01.
- BOOT_FILE=/proc/sys/kernel/random/boot_id, BOOT=independently acquired exact boot ID.
- MANIFEST_SHA, STDOUT_SHA, STDERR_SHA are SHA256 of the fixed bytes specified in
  `run_tests.py`. Substitution must produce no remaining `@...@` tokens.
- Epoch, nonce and phase are fixed in source; changing them is a new reviewed
  package, not a runtime option. This package admits exactly one epoch/nonce pair.

1. **Root reserve** checks the trusted parent directory, atomically creates BASE
   with mkdir/noclobber, then control(0700 root), source(0755 root, files0444 root),
   and work(0700 UID2000). BASE itself is the spent epoch AND nonce marker. It must
   never be deleted, including after successful audit. Failure after mkdir consumes
   the package. No multi-package/global nonce ledger is implemented.
2. **Plain shell capture** verifies UID, pinned source/manifest and path metadata,
   takes a once-only mkdir dispatch claim, and runs the fixed producer synchronously
   with noclobber byte-preserving stdout/stderr redirection. It captures `$?`
   immediately and propagates it, including nonzero. No command substitution ever
   holds payload or diagnostic bytes. All child data is finite: 2+12 bytes.
3. **Root seal** requires the trusted host's actual status7 and matching boot. It
   consumes a seal-attempt marker, checks state/source/manifest, revokes workspace
   directory access, validates exact output inventory, regular types, link count1,
   owner/mode, lengths and binary hashes, then copies only the two fixed files into
   root control. Noclobber receipt binds epoch, boot, phase, nonce, source/manifest,
   actual result and exact published files (name, size, hash). Receipt/output mode
   becomes0400 and a final completion marker is created. Any error retains HOLD.

Accept only the current trusted host's successful seal return plus independently
verified complete marker, receipt, exact two published files and metadata. A bare
marker, old receipt, valid binary bytes, or expected rc7 does not authenticate a
fresh producer. Parent retains original capture/transport and seal command results.
No command is allowed to infer rc from SUCCESS text or repair a partial publication.

## Security and failure limits

Trusted root, trusted pinned host commands, a root-owned non-shell-writable ancestor,
no concurrent/untracked shell writer, and synchronous producer completion are
preconditions. Source/control/receipt are inaccessible for writing by UID2000.
That is producer isolation under these assumptions, **not absolute immutability**.
Root can modify files. chown/chmod/stat alone do not exclude same-UID competing
writers, open descriptors or check/use races. This fixed producer opens no files,
forks no descendants and has no background work. Do not generalize to arbitrary
children. No timeout/kill/termination guarantee, storage exhaustion defense against
an adversarial shell peer, power-loss durability, fsync protocol or crash recovery
is supplied. The two finite producer writes bound normal payload storage, not an
arbitrary process. The host's subprocess timeout in tests is not Android assurance.

There is no cleanup command. Foreign/missing ownership, unknown process lifetime,
missing files or uncertain cleanup retains all names and the spent marker in HOLD.
Do not recursively delete, adopt, reset state, or rerun this package. Parent may later
plan exact owned-name cleanup separately, but must preserve authoritative spent state.
Receipt publication can be torn by a crash; absent current successful seal/audit is
uncertainty. Boot continuity reads are checks, not transactional snapshots.

## Host tests and remaining Android gates

Run from this directory:

    PYTHONDONTWRITEBYTECODE=1 python3 -B run_tests.py
    PYTHONDONTWRITEBYTECODE=1 python3 -O -B run_tests.py

These execute the real rendered templates and finite producer on nc-lab using
/bin/sh, real filesystem metadata, noclobber and captured subprocess exit status.
No device, ADB, su, sudo, install, network, existing runtime or validator is used.
Both logical root/shell UIDs map to the current host UID, honestly: these tests do
NOT prove Android privilege separation. Wrong-UID tests deliberately change the
expected UID; no chown to another user is attempted. Synthetic boot is a fixture.
Checks use unittest, never removable bare asserts. Each test retains bounded own
host-case-* fixtures under this directory, excluded from source packaging; no
recursive cleanup is performed. Repeated test runs accumulate those small fixtures.

Faults cover source/manifest replacement, same fixed epoch/nonce reuse, stale valid
bytes before dispatch, missing/lost/zero-substituted status, LF/NUL corruption,
partial publication/no retry, wrong boot/state/UID/mode/type, symlink/hardlink,
missing/extra hidden output and retained cleanup uncertainty.

Before any Android execution, independent review and parent preflight must establish
real UID0/2000 contexts, ancestor metadata, Android stat/sha256sum/wc/chown/chmod/
mkdir/noclobber behavior, trustworthy transport rc7 propagation and producer
completion, script identity and boot binding, exact maximum normal storage, and
root-only receipt handoff. No Android gate is claimed passed here. No 57-case batch
is required or substituted. Existing FD02 evidence does not qualify these templates.
No candidate14, PWM claim or change to 37/45/8/60/600 follows.

Scalar utility contract: all stat/id/sha256sum/wc/boot reads preserve actual utility
status with assignment-or-HOLD, with no status-masking pipelines. Hash output must
match the complete expected digest plus two spaces plus fixed filename. State is
byte-hashed, not compared after newline stripping. Trusted utilities must have their
qualified NUL-free scalar output dialect; command substitution is NOT a binary
metadata validator. Payload and diagnostics never enter it. Host fault tests inject
valid-looking output followed by nonzero status for id/stat/cat/sha256sum/wc.

Parent inventory update: the separate read-only acquisition
`artifacts/receipt_parent_inventory_20261108_01` observed /data/local UID0:GID0,
mode751, non-symlink, with plain-shell traversal. This is not blanket ancestor
permission proof. Before reserve, parent must freshly match metadata and establish
plain-shell `test ! -w /data`, `test ! -w /data/local` and traversal; no existing
parent is chmodded. /data was UID1000:GID1000 mode771, and /data/local/tmp was
UID2000:GID2000 mode771, so shell-writable tmp is not used for protected control.

Host tests explicitly replace the production PATH line with /usr/bin:/bin in
private rendered fixtures. Utility fault cases prepend their own finite fake utility
directory to that private seal script only. Production template PATH is not an
input parameter. The dispatched claim must be empty; seal rejects any immediate
entry (including hidden/dangling symlinks), without recursive traversal or cleanup.
