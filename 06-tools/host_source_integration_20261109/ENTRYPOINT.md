> Current inactive ABI correction and counts: see ABI_COMPATIBILITY.md. Earlier counts below identify historical review slices; original GuardedADB compatibility was not established by their adapter-based legacy test.

# Inactive concrete host entrypoint, 2026-11-09

Status: OFFLINE ONLY. 86 tests normal/-O PASS;28 entrypoint tests,21 combined tests,
and32 nested unchanged legacy tests per mode. No original runtime file changed.
No commit/stage/branch/push, real --execute, USB-host/device/ADB service or real sink.
One test invokes only original read-only Git queries on current nc-lab checkout.

The historical84ccb4 source/artifact bytes and manifest are preserved under
historical_84ccb4/, not merely a stale hash list.

## Exact implementation

- fresh_private_directory.py: inert constructor plus held-dirfd, independently
  pinned existing base, exclusive new0700 directory, name/fstat identity checks,
  observed namespace edge checks and one-attempt descriptor cleanup.
  Adapted setup only from reviewed qualify_private_sink.py a35e3024; no synthetic
  payload, qualification.run(), collision probe or synthetic destination reused.
- host_entrypoint.py: explicit private HostInputs/HostDependencies, original
  post-load source gate, required composed runtime identities, prepare/close and
  ordinary post-success source finalization. No transport/recovery controller.
- inert_source_loader.py: fixed19-module byte DAG now includes construction,
  fresh-directory and entrypoint. It prechecks22 source paths, reads each once,
  raw-Git-blob binds every byte and defers two finalizer modules as bytes.
- main_wiring.proposed.patch: inactive main-only injection.
- combined.proposed.patch: final complete inactive four-source composition,
  including canonical boot, metadata pull, observed-size callback, lifecycle/origin
  and main wiring. This complete diff is the intended code identity prerequisite.

No production module transforms or patches source. Only fixture preparation composes
the proposals in memory. The future checkout must ALREADY contain the reviewed
composition in clean tracked HEAD. A clean commit of new glue alone is rejected:
host_entrypoint requires exact four intended source SHA256 values BEFORE mkdir.
Every retained loaded/deferred byte is rechecked against the post-load HEAD blob
map, not trusted just because a mutable dictionary says it was verified earlier.

## Main branch and lifecycle

The intended main retains argument grammar, distinct transports, fresh outputs,
source report, original owner write/chmod, SIGINT/SIGTERM/SIGHUP handlers, save,
execute and the existing TimedStockTrial lifecycle. Private inputs are explicit,
rather than an implicit host home directory. Production --execute without those
inputs cannot fall back to legacy GuardedADB.

Order:
1. Original source_provenance(paths=HARDWARE_PATHS,require_clean=args.execute).
2. Offline branch returns sanitized source/planning report, no mkdir/transport.
3. Execute branch demands explicit inputs, matches loaded commit/blob map and
   required composed bytes, verifies freshness before creating output directories.
4. prepare repeats original require_clean=True before private mkdir or constructing
   association/socket factory/adapter. Approved base/process pins are never learned
   from current observations.
5. Create exactly the configured fresh directory under the independently pinned
   base. Its own-created identity becomes sink ParentPin after no-follow checks.
6. Construct using association.acquire_process and the outer spent sink latch.
   TimedStockTrial receives this adapter; its own DeadlineTransport remains intact.
7. Original owner/signal/save/execute flow. No changes to37/45/8/60/600 or recovery.
8. Only after execute succeeds, separately gate finalizer22 paths, byte-load exactly
   offline_acceptance and host_evidence, verify finalized capture against retained
   created inode/facts, and create private source-evidence.json exclusively0600.
9. Close held directory FDs once. Successful status prints only after close succeeds.

On setup failure, retain created paths, close acquired FDs once, no transport.
On caller failure, no finalizer. On finalizer failure, no caller reentry/restore/
reboot; saved run.json bytes and hardware event list remain unchanged. Acquisition
stays awaiting_offline_video_validation, never falsely upgraded to qualified video.
A failed/partial evidence file is retained, not overwritten or retried.

## Trust and scope of filesystem claims

Existing base/process pins, limits, video capacity, exact directory name and
no-concurrent-writers assertion are private explicit inputs. Fresh directory
identity is obtained only for this successful own mkdir, not by adopting a
pre-existing name. Collision, denial, wrong UID/mode/inode, symlink, observed edge
swap, late result and uncertain close fail without chmod/repair/path fallback.

The mkdir→stat/open interval is NOT atomically authenticated: a same-UID/root
replacement completed inside that interval may evade snapshots. Explicit
no_concurrent_namespace_mutation=True and trusted host/UID/root are assumptions.
Held FDs and repeat checks reject observed races, not malicious trusted-root action.

Held-dirfd claims cover setup, capture via reviewed sink and source evidence.
Existing caller event files, owner.txt and run.json keep their original ordinary
Path semantics; this is NOT a claim that every later caller write is dirfd-anchored.
No generalized filesystem wrapper was inserted into the runtime.

Setup has an inherited12s checked host-only budget; later finalization uses a NEW12s
inspection budget, not renewal of a phone watchdog/active alarm. Synchronous OS
reads/writes/cleanup may block past checks; no hard cancellation or durability claim.
The existing evidence hashing/probe contract remains separate from physical trial
timing. No video quota is inferred from the4096-byte qualification probe.

## Externally pinned bootstrap contract

The loader cannot authenticate itself retroactively. An independently approved
operator must verify its exact bytes against an externally approved hash BEFORE
executing any project source, using the trusted interpreter/stdlib (isolated mode
recommended). The loader accepts bound read-only Git/read APIs and sys.modules.
It returns modules, verified source bytes, commit and blob map.

Then the approved private invocation:
- creates HostInputs with the loaded classes/independent private pins;
- provides inert LinuxProcFS and explicit OS/socket/clock/fcntl dependencies;
- calls the loaded timed main with host_inputs, verified_sources and host_dependencies.

This is an API, not an auto-running bootstrap CLI. No config parsing/discovery,
new credentials/services, endpoint fallback or self-generated expected pin exists.
If a separate bootstrap file is introduced, its reviewed path/bytes must be added
to the audit/gate closure; this package does not secretly authorize such a file.
The current checkout's expanded gate was actually tested: it rejects before even
fake mkdir/transport because required paths are untracked/different from HEAD.

## Fixed source roles and approval manifest

runtime_audit_manifest.json separates:
- three tracked existing modified caller sources;
- the new transport file requiring the callback patch and other exact new modules;
- unchanged mandatory original guard/helper paths;
- executed validator snapshot and nc-lab analyzer inputs;
- narrow supporting tests/docs, not entire spike trees.

Hardware20 = original13 + adapter/Linux/sink + loader/construction/fresh-dir/entrypoint.
Loader preverification22 includes deferred finalizer2 bytes but does not execute them
during hardware acquisition. Finalizer22 repeats original guard before those imports.
nc-lab validation7 remains CONDITIONAL on exact source_provenance AST extraction with
verified globals; ordinary import of the guarded caller needs its transitive closure.
That separate analyzer entrypoint is not expanded here. Snapshot is executed code.

The manifest is for audit/approval, not admission. It excludes private configuration,
media, identifiers, prior denied policy13 files and unrelated artifact trees.
The existing denied policy checkpoint remains stopped. No Git action was retried.

## Tests and limits

Entrypoint tests cover actual main body on fake Path/OS/socket/time, association to
the constructed adapter, original owner/signal/report writes and deferred evidence;
source dirty/untracked/changed/uncomposed guards, loader origins, explicit config,
base pins/symlink/collision/denial/mode/swap/late mkdir, one-shot setup, caller failure,
retained partial capture, finalizer source tampering/preload/replacement/close/write
failure, unchanged saved acquisition/hardware events and required namespace assertion.

The real six-argument constructor is separately smoke-tested without transport.
The cleanup Scenario retains documented fake stage choreography and Sweep.state
override; main test's instrumented caller factory returns that real-method fixture.
This is not whole DDIC/envelope qualification, physical timing or host platform PASS.

Commands:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools/host_source_integration_20261109 -q
PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s 06-tools/host_source_integration_20261109 -q

Remaining: independent frozen review, permitted exact source checkpoint decision,
external bootstrap/source authorization, actual private configuration/capacity,
host platform/directory qualification and separately admitted stock-only execution.
No live-ready, candidate14, physical Hz or optical approval claim.
