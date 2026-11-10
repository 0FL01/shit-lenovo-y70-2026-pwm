# Read-only stock readiness observer

Status: new offline implementation, not deployed or executed against devices.
No acquisition, setup, recording, DSI/ESD selector, watchdog, ownership change,
recovery, commit or push. No full-trial modules are imported. Original camera
duration/restart settings remain **unknown** because the reviewed public code
does not provide a supported narrow read-only API for them. No preference-file
dump, private camera receipt or previously denied private launcher is used.

## Files and execution boundary

- `launch.py`: explicit reviewable entrypoint, strict JSON/private-file checks,
  read-only Git tracked-source verification and externally pinned byte loading.
- `probe.py`: fixed read operation/role allowlist, strong existing adapter and
  process/socket association, before/after boot guards, sanitized result, private
  exclusive evidence. No arbitrary command/operation input.
- `test_probe.py`: synthetic I/O and public tracked source tests only.

An authorized operator must independently authenticate **launch.py bytes before
running it** with a trusted isolated interpreter. The launcher cannot authenticate
itself. It authenticates probe.py and three dependency modules against separately
approved SHA256 pins in private config, not a self-generated runtime manifest.
The three dependencies must also match their tracked blobs in the exact configured
commit. The new probe is kept outside the previously frozen dependency root.
Do not mutate/adopt that root or derive server/serial pins from live observations.

Invocation shape (not run as part of this work):

    python3 -I /approved/new/launch.py --source-root /approved/frozen/repository \
      --probe-source /approved/new/probe.py --private-config /private/config.json

This performs only source/config validation and inert construction: no proc scan,
socket, device request or evidence write. Only a separately admitted invocation
adding `--execute-read-only` runs observations. It still never performs setup or
capture. It prints one JSON summary; errors produce only the static failure JSON.
Never print the config, raw device output or private evidence. Keep shell tracing
disabled and do not put config contents on command lines.

The known deployed dependency commit supplied by the lead is
`d5a522ce002ca580c231fc87250c38d1665980d3`; this implementation does not assume that
the local development checkout or newly generated pins prove deployed identity.
Use independently supplied, reviewed matching source/config inputs for that root.

## Strict private JSON schema

Config file: regular owned 0600 file, one link, immediate parent owned 0700.
All path components are opened without symlink traversal; bounded reads compare
file metadata before/after. No credentials, keys, passwords or session tokens are
needed or allowed. Unknown keys, duplicate JSON keys and nonfinite values reject.
All following fields are mandatory, with no additional fields:

- `schema`: integer 1.
- `source_commit`: exact 40 lowercase hex tracked dependency commit.
- `source_sha256`: exactly `probe`, `offline_baseline_adb`,
  `linux_adb_probe_dependencies`, `camera_capture_metadata`, each 64 lowercase hex.
- `process`: `pid`, `starttime`, `uids` (four integer zeroes), `executable`,
  `executable_device`, `executable_inode`, `executable_mode`, `executable_uid`,
  `version` (exact independently pinned ADB version output as JSON string).
  Numeric fields are integers, never JSON booleans. Endpoint stays fixed existing
  loopback 5037, ADB protocol 41; no daemon spawn/client CLI/fallback.
- `association`: `listener_inode`, `network_namespace`, `executable_sha256`,
  `executable_size`. These are private independent LinuxAssociation pins.
- `limits`: positive integer resource ceilings `tcp_bytes`, `stat_bytes`,
  `status_bytes`, `max_pids`, `max_fds_per_pid`, `max_total_fds`, `link_bytes`.
- `serials`: ordered two distinct strings, target then camera, independently
  supplied. No transport IDs, boot IDs, credentials or session tokens in config.
- `host_uid`: integer matching the invoking effective file owner identity (uid).
- `evidence`: `directory`, `device`, `inode` for the independently pinned existing
  private 0700 directory. Exact filename `readiness.json` must not exist. No mkdir,
  chmod, overwrite, deletion or alternate destination. The directory must be fresh
  for this observation and exclusive to the operator, with no concurrent namespace
  mutation. Collision or changed identity fails, never repairs.

Process pins also undergo the existing OfflineBaselineADB/LinuxAssociation
validation. Constructor calls are inert. Execution validates the evidence
directory before device reads, and checks it again before exclusive 0600 creation.
Required runtime assumptions: trusted host/kernel/root/server, no concurrent
namespace modification, trusted interpreter/stdlib/Git and source pin delivery.
No new security boundary against same-UID/root or malicious Python callers is
claimed. Symlink and observed identity mismatches are rejected, not race-proof
authentication against trusted-root replacement. No hard OS cancellation or
durability guarantee; synchronous syscalls can block beyond deadline checks.

## Observations and interpretation

Current two-role transport aliases are freshly enumerated and independently
confirmed by serial, then all device shell reads use immutable serial selection.
Existing adapter rechecks server/process/namespace/listener identity around
operations. Before/after fresh boot IDs must match; both are retained privately
with serial roles and transport aliases. Transport errors are terminal for the
one-shot probe. No retry, adoption, daemon reconnect, reboot or cleanup occurs.

Target identity includes the fixed SKU/build/slot/kernel/device/Enforcing profile,
UID0, panel name and module digest. Reads observe all five original system settings,
native DBV/power/DC/logger and ownership mutex existence. The probe neither reads
owner tokens nor claims a present mutex belongs to us. Power/lock/foreground are
optional enum classifications; unknown layouts stay null. No UI dump that writes
to the phone is used. Settings are reported, not changed to target values.

Open Camera package versionCode/versionName are parsed from its ordinary package
query. Unsupported/ambiguous strings stay null. Camera metadata is internally
parsed by the existing pinned pure parser, observing actual exposure/ISO/lens/crop
profile and checking request/result agreement and manual modes. Stopped PREVIEW
requires PREVIEW in both request/result, no verified recording and no encoder
stream. Unknown/mismatched metadata never yields a ready camera. Only allowlisted
numeric profile fields leave the parser; no session token, PID, address or raw
metadata/package/power/foreground dump is saved or printed.

The result is a sequence of read-only snapshots, **not an atomic state lock**,
ongoing camera-stop guarantee, approved setup, capture qualification or optical
evidence. `setup_admitted` and `acquisition_qualified` are always false; `pwm_hz`
always null. Parent must independently review current states and its separate
bounded setup/capture protocol. Historical values are not silently reused.

## Offline verification

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools/stock_observation_readonly_20261110 -q
    PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s 06-tools/stock_observation_readonly_20261110 -q

Tests use synthetic serials/boots/config pins, fake shell/transport or a forbidden
socket factory. Source-only launcher test performs local read-only Git and file
reads, not device/USB-host operations. Test-computed digests are fixture data,
never operator source approval. Existing adapter/association tests remain separate
evidence and do not prove this launcher on the actual USB host.
