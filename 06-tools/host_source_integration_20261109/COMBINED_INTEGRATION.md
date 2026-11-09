> Current inactive ABI correction and counts: see ABI_COMPATIBILITY.md. Earlier counts below identify historical review slices; original GuardedADB compatibility was not established by their adapter-based legacy test.

# Combined inactive integration: frozen fixture scope

2026-11-09. 21 combined tests normal/-O PASS; full directory58 tests normal/-O
PASS, including32 nested unchanged legacy transport/caller tests per mode.
No original runtime/test/source edits, no Git write, deployment or device action.

## Exact virtual composition

combined_binding.json pins every original source, reviewed patch transformer,
fixture source and new construction source. combined.proposed.patch is one
inactive diff, composed in memory only:
- stock_c1_sweep.py: canonical UUID recovery predicate.
- run_p85_guarded_trial.py: observed-size pull metadata + latest deferred video branch.
- run_p85_timed_stock_trial.py: deferred stop call + successful post-finally lifecycle/
  acquisition-schema/origin report fields.
- offline_baseline_adb.py: observed_size=expected_size passed at its sole sink callback.

Virtual SHA256:
stock_c1_sweep 1c105480c1ec7abded156f16cf96a98719f0528620b176698dc4226bf933a0d4
run_p85_guarded_trial b5af1fdca25f8d7802d49d62a4f54367927e6300f334a86db792f4a92978ebe7
run_p85_timed_stock_trial 4154b1cbc0034d1674c35546eef958dead8e28963397ed4d67492d6632acae37
offline_baseline_adb 7f2d60bffcf4e74fc4060941a6a8444ee6bb052ae24a07d23407aaef0ce0585e

No sourceguard weakening, candidate14, new controller, timing change or transport fallback.

## Executable construction slice

inert_host_construction.construct first calls ORIGINAL loaded source_provenance,
with require_clean=True and exact HARDWARE_PATHS. Association/socket factory/adapter/
retention objects are constructed only after that guard passes. The caller supplies
already-created inert proc/OS/socket capabilities, private pins/parent identity/capacity;
the claim is NOT gate-before-creation of these already-injected capability objects.
Their construction/use must remain behind future launch admission as appropriate.

Actual LinuxAssociation.acquire_process, make_socket_factory, patched adapter and
real PrivateSinkFactory run against reviewed FakeProc/FakeOS/socket/time fixtures.
Construction keeps one outer spent latch, actual returned sink and a copied
(dev,ino,uid,mode) tuple from that sink's held-created FD file_meta. It does not derive
the expected identity from a later reopen. Dynamic sink.facts remains accessible
after caller closes it. Factory failure retains error.facts, never invents an inode;
no returned sink/identity means no promotable finalized artifact.

file_meta is a reviewed internal field, not a new public sink API. This direct
coupling is explicitly pinned and tested; future source change needs fresh review.
If the factory fails before returning, even a retained partial file cannot be
promoted using a guessed/reopened expected identity.

## What the concrete fixtures execute

Full composed modules are loaded from verified virtual bytes. Actual combined
execute, stop_camera, recovery, restore, alarm and deadline wrapper method bodies
run unmodified. A separate smoke invokes the REAL six-argument constructor with
controlled uuid/time, fake g and harmless Path values: zero transport calls,
correct inheritance/wrapper/default reports and candidate rejection.

The existing cleanup Scenario's stage choreography is retained: setup, observation,
writer/hold operations, metadata/identity camera staging are fakes. To match that
reviewed cleanup fixture, its allocated subclass uses actual Sweep.state rather
than BatchedTrial.state/envelope. This is a deliberate fixture override, NOT a source
patch. It does not qualify full real DDIC/envelope/state choreography or trial latency.
Fixture allocation bypasses caller __init__, separately covered by the constructor smoke.
The real-source loader here performs local Path.resolve metadata reads only, unlike
the older isolated actual-import test's explicit exact-path stub. No device path,
network endpoint or real OS sink operation occurs.

This deliverable has exactly21 combined tests, not a new
performance bound. Fake stages cannot establish whole-return timing.
37/45/8/60 constants are checked through real constructor defaults; fixed600 watchdog
builder and actual fake-signal restoration are tested. No guard values changed.

Coverage:
- successful stop→bounded pull→camera XML cleanup→settings/logger/DBV restore→
  watchdog disarm→mutex release, with deferred pending-video status;
- actual legacy stop_camera default still calls validator with ffprobe timeout20;
- cap/size mismatch, incomplete pull, write failure/late write, close uncertainty,
  factory late create, missing stop UI, restoration/disarm/release failure;
- one-shot sink refusal with original identity retained and no second OS creation;
- process trust invalidation via correct acquire_process bridge;
- active camera timeout/late/alarm failure: one target reboot, no next write stage;
- malformed new boot: no panel restoration or owner release;
- original expanded source guard blocks before new dependency construction.

Late write nuance: an OS write returning a valid count can yield confirmed_written
and write_outcome_uncertain=False, even when its late return fails the deadline.
The transfer and caller still fail. Facts alone never upgrade failed acquisition.

## Ordinary evidence and validator contract

Three additional concrete tests are INCLUDED in the21 count:
- actual host source_evidence accepts only after successful combined execute/cleanup,
  using retained created inode/facts and fake read-only finalization FD;
- replacement inode, pre-cleanup status and failed cleanup cannot qualify;
- latest immutable validator snapshot works despite changed combined caller bytes;
  tampering is refused, original ValueError validator semantics retained.

Evidence helpers are byte-bound to validator_contract_binding.json's fixed revision:
offline_acceptance ccc92a5a53bf5e9ba4ea3301ae73407c09a4af977e06db3bf653eee18c2a0dc1
host_evidence a3beefcf83e13074b15bac4f70b15d5b07449f017513a985a43deb7be0ffe52e
video_validator_snapshot f5e82bcbbaa0c5cc2ca6c42071c8a008c55eddabc9b0f809cc6d14641be22923
analyzer_join 4adc3382e234a7cadb04eca33bd8713563f62134efb57b1d842819dd2d64abce

Analyzer join is closure-bound here but NOT executed by this combined test.
No real capture/video decode, real ffprobe, private transfer or actual finalizer FD.
The prior proposal.sources-original-path incompatibility is fixed upstream by the
separate immutable snapshot, not by weakening hashes or acceptance.
Snapshot bytes are EXECUTED CODE and belong in the consumer gate/raw-byte map.

## Fixed per-phase source sets and remaining entrypoint contract

See phase_source_closure.json and executable constants in inert_host_construction.
- Hardware18 paths = original13 + adapter + Linux dependencies + sink + byte loader
  + concrete construction. Keep original guarded_adb_socket even if unused transport.
- USBhost ordinary finalizer20 paths = hardware18 + host_evidence + offline_acceptance.
  Only source_evidence is used on that host. No snapshot execution for this phase.
- nc-lab validation7 paths = offline_acceptance + host_evidence + analyzer_join +
  executed validator snapshot + original source_provenance provider guarded caller +
  two exact analyzer sources. The seven-path closure is CONDITIONAL: the guard
  provider is executed as its exact pinned source_provenance AST function, with
  explicit Path/re/subprocess/check dependencies from verified source/stdlib, NOT
  by importing the entire guarded caller module. Full module import would require
  its complete transitive project source set. This execution choice remains an
  open exact entrypoint contract, not a claim that arbitrary validation launch
  closes at seven paths. Include any actual launch wrapper as an additional
  executed source before admission; that wrapper does not exist yet.
No proposal.py runtime dependency remains. Test helper sources are fixture provenance,
not deployed hardware paths.

Current16-module loader does NOT yet execute the new construction source snapshot.
Construction's own path is in original post-load gate, but the future byte-loader
must load this exact module before calling it, alongside externally pinned bootstrap.
That small entrypoint wiring remains unimplemented, not silently waived by tests.

Original post-load guard was exercised using fake Git. Fake HEAD/source_clean report
is fixture data, never permission or real admission. Existing real expanded source
gate remains blocked because new sources/modified callers are not clean tracked HEAD.
No commit/stage/push/taskbranch workaround was attempted. Pending policy13 files
are separate and their denied commit was not retried.

Before any real trial: reviewed exact entrypoint/source composition, bootstrap pin,
role-specific clean tracked HEAD, approved private inputs/host-only fresh-directory
setup, platform/sink qualification and separately admitted stock-only execution.
Independent review of this frozen combined slice is required; passing it does not
close these deployment prerequisites.
