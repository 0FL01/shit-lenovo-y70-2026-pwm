# Prospective observation analysis preparation

Status: **working offline conditional diagnostic adapter; synthetic tests only**.
No new actual movie exists in this task. No optical/physical result is claimed.

Adapter/API/contract: `06-tools/stock_observation_analysis_20261110/analyze.py`
and README.md. Separate producer: `stock_observation_20261110/coordinator.py`.

31/31 focused synthetic tests PASS normal Python and `-O` after the atime fix.
The earlier29-test verdict was superseded by independent review:28/29 passed,
1 failed because reads updated atime. Both comparisons now use explicit
dev/ino/mode/uid/nlink/size/mtime_ns/ctime_ns, excluding atime, retaining hashes.
New regressions age file atime and verify all mutation/custody fields still count.
Independent hash-bound recheck has been requested; its review is separate. Existing optical
spectrum regression:10/10 PASS. Full logs accompany this report. Tests include
private capsule ingestion and JSON/NPZ output, exact source closure/record/media
hash binding, actual inode identity format and sink lifecycle, final boot drift,
controls/session/encoder counters, source/custody tampering rejection, ROI review,
late-pair conditional route, unrelated error rejection, exact windows and metric
reuse/all-ROI arithmetic. Synthetic media pipeline uses mocked probe/extraction;
no real movie or actual visual inspection is represented by those tests.

`analyze_actual` consumes the concrete writer capsule and an independently pinned
expected source identity. It emits only conditional diagnostics. Source/custody,
boot drift, missing review, incomplete cleanup or unrelated failure reject. A
late advancing pair can yield ratios/curves only with the explicit producer
late-controls failure markers and otherwise complete stop/cleanup/source evidence;
first-window control coverage stays unknown. Early pair is still only conditional
snapshot evidence, never per-frame sensor/MP4 calibration.

Frozen four windows, ROI, q, Hann, degree2 and all-ROI5% retained. Duration9..15s
plus delta from10s; duration≤15s does not establish preventive native10s cap.
All summaries: acquisition_admitted=false, qualification_eligible=false,
candidate_admission=false, strict_acquisition_status=inconclusive,
physical_pwm_hz=null, even when nominal arithmetic≤5%. One continuous movie;
windows/ROIs not independent. No optical-return/comfort/AA10/14 approval.

Actual byte-bound source/custody evidence, true human ROI review and real decoding
remain unperformed. Code/test readiness is not physical capture readiness. The
producer's future independently frozen expected source identity must NOT be
copied from an arbitrary input capsule. Detailed evidence/profiles/per-frame
curves remain private; sanitized summary omits raw metadata/boots/identifiers.

Source03 diagnostics/thresholds and WORKSTATE were not edited. No device/ADB,
commit, push or PR operation occurred in this task.


## Transfer fallback preparation

The prior31-test independent review passed after the atime fix. A subsequent
host-only capability check by the lead found no NumPy/ffprobe/ffmpeg on USB-host.
The new transfer.py is a stdlib-only endpoint-specific sender/receiver; it reuses
host_evidence.snapshot, OwnedDirectory and PrivateSinkFactory. It transfers only
the unchanged raw capsule, exact four bound records and capture.mp4, with separate
source-completion/destination-custody receipt. Optional analyzer branch preserves
original-inode behavior and never edits capsule.media.created_identity.

Current47/47 normal and -O PASS: adds actual local directory/sink tests, stdlib
python-S sender, source/destination same-byte inode substitution, post-close
swap, failed source exit, truncated/trailing streams and chain tampering. First
transfer suite run had7 Path API errors, corrected by returning concrete Path;
current47-test runs supersede that development run. Media is synthetic arbitrary
bytes; probe/extraction remain mocked in integration tests.

FREEZE_TRANSFER.json pins the new review candidate. Independent review requested;
prior independent PASS does not automatically cover this optional branch.
No actual remote transfer, source deployment/publication, capture or host package
installation occurred. Exact caller API and transport timeout/trust requirements
are in 06-tools/stock_observation_analysis_20261110/TRANSFER.md.


Independent transfer review ran47/47 normal/-O but found a failure-admission gap:
final directory-close failure could leave a receipt before receive_bundle failed.
Fixed by explicit pending-receiver-exit receipt status and mandatory externally
observed integer receiver process exit0 in the analyzer. Receipt existence is
never receiver-success evidence; final cleanup exceptions still propagate.
A deterministic injected close-failure regression follows that exact sequence
and verifies consumer rejection. Missing/nonzero receiver exit also rejects.

The same review identified nonfinite deadline and prehash byte-cap gaps. Both
are fixed: deadlines finite/unexpired at entry, actual source size≤256MiB and
equal to capsule before any media hash. New52/52 normal/-O PASS, including these
regressions. FREEZE_TRANSFER.json updated for independent hash-bound recheck.
The preceding47-test verdict is historical and does not cover these fixes.
