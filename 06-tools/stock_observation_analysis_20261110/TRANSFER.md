# Source-bound transfer fallback: offline prepared, not executed remotely

Endpoint-specific custody for one stock-observation-v2-native10s recording.
USB-host lacks NumPy/ffprobe/ffmpeg (lead's host-only observation); nc-lab has
analysis dependencies. This wrapper never installs packages, opens a network
connection, calls SSH/ADB, records video or changes capture/publication gates.
Original-inode analysis remains supported unchanged.

## Files and trust boundary

`transfer.py` sender is standard-library-only. It reuses hash/snapshot from
`video_validation_split_20261109/host_evidence.py`, whose old AA/P85 admission
functions are NOT called. Receiver uses real `OwnedDirectory` and
`PrivateSinkFactory`. All six executed helper/dependency source files must match
independent reviewed pins, before execution. Their relative paths are in SOURCES
and FREEZE_TRANSFER.json. Reject preloaded dependency modules; use a fresh process.
No NumPy/Pillow/ffmpeg import by sender. A `python -S` subprocess test covers this.

Existing authenticated host→nc-lab route is caller-owned. Caller must provide the
verified specific source peer, enforce whole-process/transport timeout, and pass
actual process exit status. It must never substitute a success lambda in real
use. Blocking stream reads/writes cannot be cancelled by synchronous deadline
checks alone: external caller timeout remains required. Each endpoint supplies
its own local monotonic deadline; no cross-host clock comparison is attempted.

Trusted owner/root and explicit no concurrent writers are assumptions, not a
signature, adversarial-root defense, immutable filesystem or durability claim.
Private receipt data records actual source/helper/transport facts under this
existing trust model. Hashes identify bytes, not truth of arbitrary forged JSON.

## Exact source sender interface

send_bundle(capsule_path, binary_stdout,
  expected_source={commit, closure_sha256},
  expected_helpers=reviewed_helper_path_hash_mapping,
  deadline=local_monotonic_deadline, no_concurrent_writers=True)

The source process uses a reviewed code deployment with preserved relative paths.
`expected_source` is the independently reviewed capture closure, not copied from
the capsule. Helper pins are separate; they do not modify the capture closure.

It reads ONLY the named numbered analysis-evidence capsule, its exact four bound
before/recording-snapshots/outcome/source-closure JSON records, and capture.mp4
from that private0700 directory. All files must be owned regular0600 with one
link. Original media must be the capsule's actual created inode, exact size/hash.
No arbitrary file list, whole-directory copy, review files or path substitution.

Wire: bounded length-prefixed JSON header containing original capsule/record
bytes as base64; exact declared media byte count≤256MiB; bounded final source
completion packet. Header cap32MiB. Sender rechecks source inode/stable metadata,
bytes/hash and every original record before completion. Read-updated atime is
excluded. Capsule and records are never reserialized or rewritten.

## Exact destination receiver interface

receive_bundle(binary_source_stdout,
  base_path=approved_private_base,
  base_pin=[device,inode,uid,mode], directory_name=fresh_name,
  expected_source=independent_capture_source,
  expected_helpers=independent_reviewed_helper_pins,
  authenticated_peer=verified_source_peer_label,
  finish_sender=actual_transport_process_wait_function,
  deadline=local_monotonic_deadline, no_concurrent_writers=True)

The callback must return the actual sender process exit code; only integer0
passes. EOF and no trailing data are required before completion. The receiver
creates a fresh directory0700, exact original five JSON files0600, capture.mp4
through the bounded private sink, then transfer.json0600. It records actual sink
created inode before close, verifies the same inode/hash after reopen, checks
source completion/header binding, final sender exit0 and sink lifecycle facts.
No overwrite or retry of a spent destination. Partial failures can retain artifacts INCLUDING transfer.json when its write or
final directory close is uncertain. That file explicitly has status
destination_bytes_verified_receiver_exit_pending, not receiver success. Caller
reports failure and uses a new destination only if a later retry is permitted. Neither originals nor partial files are deleted.

Returns (new_destination_Path, receipt). Source completion contains original
inode/hash/bytes and unchanged before/after metadata. Destination receipt adds
fresh destination inode/hash/bytes/sinkfacts, unchanged raw capsule SHA, capture
source, independently pinned helper mapping and observed sender exit status.

## Analyzer consumer

Original route unchanged. For transferred media add these explicit arguments:
transfer_path=destination/transfer.json,
expected_transfer_sources=independently_reviewed_helper_mapping,
authenticated_peer=verified_source_peer_label,
receiver_exit_code=independently_observed_actual_receiver_process_exit_code.

Consumer requires integer receiver exit0 observed by the trusted caller AFTER
the entire receiver process (including final file/directory closes) exits. It
must not infer success from receipt existence, default to0, hardcode0, copy a
JSON success field, or catch/drop receiver failures. This external process fact
is necessary because a process cannot certify its own final cleanup by writing
an earlier file. Missing/nonzero/boolean exit rejects, even if receipt bytes are
complete. The receiver process must propagate all exceptions to nonzero exit.

Consumer verifies the exact raw capsule and four original records via existing
load_capsule, reconstructs/binds the wire header, verifies source completion and
original capsule inode separately, then matches local media to the freshly
created destination inode/stat/hash and sink receipt. Never edits or overrides
capsule.media.created_identity. Copying identical media without this chain fails.
The transfer receipt and all original bytes are rechecked after analysis.

Fresh actual native-Y ROI review happens on nc-lab after transfer, bound to the
same original media hash and exact four record hashes. A review is not silently
copied/generated by the transfer wrapper. All diagnostic limits remain: fixed
windows, conditional controls, late first-window coverage unknown, strict
acquisition inconclusive, no candidate/full qualification or physical Hz.

## Tests and current boundary

52 focused tests normal/-O PASS, including real local private sink/directory,
stdlib-only subprocess sender, copied-inode rejection without receipt, same-byte
source/destination replacement, post-close sink inode swap, changed capsule/
record/helper/header/media, truncated/trailing stream, nonzero sender exit, injected final directory-close
failure with rejected consumer, missing/nonzero receiver exit, nonfinite
deadlines and oversized source rejection BEFORE hashing.
Test source media is explicitly synthetic arbitrary bytes, probe/decode mocked.
No actual capture, host→nc-lab transfer or remote helper execution occurred.
Source deployment/publication and any live use remain separately gated.

Deadline arguments must be finite and unexpired at each endpoint. Source media
size is checked positive,≤256MiB and equal to the capsule BEFORE hashing.
