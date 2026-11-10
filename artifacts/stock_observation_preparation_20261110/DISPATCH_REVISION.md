# Dispatch/source/custody revision (offline, 2026-11-10)

Previous reviewed revision is preserved by commit432d64287a771a125c5da6858369fa75d5a16bec
and FREEZE_V2.json. This revision does not reuse its coordinator hash. Scientific
protocol remains v2 native10s: windows30:90/90:150/150:210/210:270, unchanged ROI,
q=.019775390625, Hann/degree2/FFT8192 and all-ROI5%. No candidate/physicalHz admission.

## Implemented, tested offline

- `construction.py` validates all bytes in a fixed DAG before execution. The
  legacy video selector is extracted as one verified AST function; no legacy main,
  Trial or Sweep is run. Provenance closure includes construction and launcher.
- Actual LinuxAssociation, OfflineBaselineADB, fresh OwnedDirectory and retained
  PrivateSinkFactory are composed with their real signatures. Existing process,
  listener/namespace/executable and immutable roles are pinned, never learned.
  Concrete directory/sink/pull/capsule tests use real private host files but fake
  remote bytes, with no socket/proc/device access.
- `launch.py` default is source/config/review check only. It verifies new HEAD,
  each Git blob and SHA256, private no-symlink inputs, actual inspection/PNG bytes,
  prior visual decision and source provenance. Only --execute-capture calls prepare,
  select and coordinator.run. Public stdout is an explicit sanitized allowlist.
- PriorGeometryReview binds the genuinely reviewed earlier inspection and image
  bytes. It does NOT assert that later noisy PNG bytes were viewed or are equal.
  After camera UI setup, dispatch_guard rechecks target native/software state,
  exact Settings component/focus/unlocked state, manual camera profile/progress,
  current camera ActivityRecord/Intent, both boots and retained mode events. It
  retains new target/camera PNGs privately, then repeats checks. The entire fresh
  machine gate must be <=30s old at the one start dispatch. A fake ready flag in
  outcome cannot replace the actual gate object. Final MP4 geometry is pending.
- Current camera Intent is linked to the resumed ActivityRecord token and its
  own Hist block, not a historical global match. MAIN/LAUNCHER is required;
  VIDEO_CAPTURE override, unknown format or observed pending newIntents reject.
  Absence of a dumped pending-intent field is NOT claimed absolute absence of
  queued intents. This parser has synthetic layout tests, no actual MAIN proof.
- Mutex acquisition intent/token is privately latched BEFORE dispatch. Timeout
  can leave cleanup_pending even if lock confirmation never arrived. No blind
  release/adoption. Known-owned clean release still requires verified restoration.
- Specific RequestResultNotSettled supports at most5 read-only continuity retries
  inside the same15s recording budget. Other profile/transport failures are not
  retried. One Start only; no Stop toggle. Initial PREVIEW cannot prove stop until
  advancing recording has been observed; same restriction applies to late cleanup.

## Early control coverage and actual analysis

The historical startup needed2s settling and up to8s read checks, so <=1s pair
may be impractical. Windows are NOT moved. If the pair is late, acquisition status
remains inconclusive with exact `capture_validity_failure=early_controls_unbound`,
`failure_reason=frame30 controls unbound`, `control_coverage_status=unknown_first_window`.
The factual capsule can still support explicitly CONDITIONAL saved-media ratios/
curves after source/custody/PTS/geometry checks. No qualifying PASS, even if all
ratios<=5%. `first_advancing_recording_elapsed` is exactly the retained second
valid snapshot's elapsed bound. Even an early pair is not per-frame proof or
sensor-to-file calibration. Absence of an advancing pair never verifies stop.

## Concrete capsule

Numbered private JSON records include before, recording-snapshots, source-closure
and outcome. `N-analysis-evidence.json` uses
`schema=stock-observation-analysis-evidence-v1` and exact four record names/byte
counts/SHA256, independently verified source closure, final unchanged boots,
actual media size/hash, created inode tuple and actual sink facts. Host snapshot
bounds/progress are included with explicit no-per-frame/no-timebase calibration.
Actual media geometry remains required. Capsule is produced only after verified
stop, original settings/DBV restoration and owner release. Incomplete runs retain
owned evidence; no pre-existing media is deleted or rewritten.

## Not executed / remaining readiness

No capture, preferences/setup mutation, deployment or device call was made by
this worker. All tests are offline; actual UI hierarchy/current Intent/current
native mode/scene/camera geometry/output path/cap timing are NOT proven. Unknown
layouts reject. Supplementary prestart action was separately blocked upstream;
this work does not bypass or retry it. A real reviewed prestart image is required
by launcher intake; synthetic fixtures cannot stand in for it.

Final aggregate discovery:68 tests PASS normal and -O (42 protocol/coordinator,
10 construction/sink/capsule,9 launcher/intake,7 navigation/cleanup regressions). The earlier53 count was the sum
of separate fresh-process suites, not aggregate discovery. Test-only module
namespace isolation now lets aggregate discovery pass without weakening the
production preload rejection. Exact commands:

    python3 -B -m unittest discover -s 06-tools/stock_observation_20261110 -p 'test_*.py' -q
    python3 -B -O -m unittest discover -s 06-tools/stock_observation_20261110 -p 'test_*.py' -q

Stop verification now requires PREVIEW request/result AND no encoder consumers,
matching the existing readonly guard. A specific residual-encoder transition may
only be polled read-only within the original15s; it never authorizes rollback.
Past15s stop remains unverified until a separate strict late-stop observation.
A regression uses the REAL camera parser and public synthetic recording fixture
with PREVIEW intents but residual encoder stream.

The source slot prestart_inspection now binds ONLY reviewed final diagnostic v2:
6429d7f3d7d4e15b603c63ba55ee9437d7797214ca6dd3695e4990dda8832791.
Prior intake accepts only its successful prestart_inspected receipt; v1, old69af,
unknown helper hashes and v2 failure receipts are rejected. No historical receipt
is relabeled or promoted. The v1 scientific/runtime checkpoint remains historical.

 Source-only Git deployment against a newly
committed/frozen root must still be performed by the lead. Final independent
review remains required. Never interpret a source-only pass as live readiness.


## Camera UI restoration correction (supersedes prior61-test PASS)

A successful preference readback alone did not prove return to the original
camera UI. The prior revision could incorrectly release the owner after a
Settings-navigation timeout when no preference value had changed. No device run
used that revision. The corrected path latches ui_restore_pending and transition
intent BEFORE every settings/navigation input, independently of changed values.

Only preview, main_settings, video_settings and the two exact Android option
 dialogs are classified. Unknown is not navigated. A returned input command still
requires observation of its expected UI destination (or requested switch value).
An uncertain input remains sticky: only read/classify is allowed, no repeated
input, blind Back or blind re-entry into Settings. The owner remains held when
cleanup cannot be established.

Cleanup now runs independently of the changed-preferences list, starting from
its freshly observed known level. Initial critical preview control/layout
signature plus strict no-encoder manual metadata are saved before setup and
reverified after cleanup. Record, restore, release and capsule checks cannot pass
with a pending/uncertain UI transition. Successful outcome explicitly contains
camera_ui_original_preview_verified=true and camera_ui_restore_pending=false.
Original settings/DBV/owner success is not reported when camera UI is uncertain.
The same approach does not claim that an unknown actual UI layout was qualified.

The seven new synthetic XML tests execute the real navigation/cleanup methods:
Settings-tap timeout, leave timeout with all desired preferences already equal,
known dialog read interruption, uncertain Back, complete preference/UI rollback,
unknown UI and an unsupported option dialog. They verify no blind input and no
premature restoration/release. No live camera/UI test was executed.
