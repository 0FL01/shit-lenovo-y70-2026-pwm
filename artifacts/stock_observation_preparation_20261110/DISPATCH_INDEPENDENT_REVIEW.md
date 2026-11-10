# Independent capture path code review

## Superseding finding: camera UI cleanup pending

The PASS below is superseded for coordinator13e6ffc3 until the following narrow
cleanup gap is fixed. Parent identified it; independent synthetic fault injection
confirmed both enter_video_settings timeout after potential Settings input and
leave_video_settings timeout when desired preferences were already unchanged.
Both paths produced status=inconclusive, originals_restored=true,
mutex_released=true and no cleanup_pending, with an actual mocked release call.
Empty preference rollback lists do not establish restored camera UI/navigation.

Minimal required correction: latch camera UI restoration intent before the first
navigation input; independently track and verify the current navigation level;
run UI cleanup even if no preference values changed. Do not blindly re-enter
Settings from an unknown/settings/dialog level or send Back to guess a level.
Uncertain transition permits read/classification, not automatic input replay.
If exact supported level cannot be established, retain cleanup_pending/ownership.
Verified original preview UI and controls must gate restoration-complete/release/
capsule claims. Add fault tests for enter-after-input, all-values-unchanged leave,
interrupted option dialog, uncertain Back and ordinary successful restoration.
No device action was taken to reproduce this issue.

Final verdict: PASS for the frozen offline code, not current physical readiness
or execution authorization. No devices, ADB, research-usb, private config/receipts,
deployment, commit or push were used in this review.

## Exact final sources and tests

All23 entries of FREEZE_DISPATCH_FINAL.json independently match current bytes.
- coordinator.py: `13e6ffc3310125598e7cc2da2a2817c3ba5f14c127dda1557384be8381c02403`
- construction.py: `7cc85a5c77830239cb58684a27de5724543eeafc89c95bf404bff34ddae7d505`
- launch.py: `623064e2ec9b327e9d811b96e8735d1c1ac39daa348881d710ebbb90c84d06df`

Independent unittest discovery now passes61 tests in both normal Python and -O
with PYTHONDONTWRITEBYTECODE=1. Earlier53-suite revision passed only separate
38+8+7 processes; aggregate discovery failed due test module pollution. Final
fixtures isolate/restore module namespaces; production preload rejection remains.

## Findings resolved

1. Mutex acquisition intent/token is now latched privately before dispatch.
   A timed-out acquire cannot silently report no possible ownership; cleanup
   remains pending, without blind release/adoption.
2. Real pinned parser reproduced PREVIEW with encoder streams being accepted as
   stopped in the earlier coordinator. Final metadata requires no encoder consumer.
   The regression uses actual camera parser fixture bytes. Specific residual
   encoder transition polling is read-only within the same15s budget; it does
   not verify stop, restart the budget or issue another Start/Stop tap.
3. Prior inspection intake now binds only final diagnosticv2 helper6429d7f3…2791.
   V1, superseded69af, unknown hashes and failure-shaped receipts reject. No old
   failed acquisition is relabeled or promoted.

## Reviewed execution boundaries

Fixed15-path source closure includes construction and launcher plus exact helper
bytes. The legacy video selector is AST-extracted; no legacy main/Trial/Sweep is
called. Real LinuxAssociation, OfflineBaselineADB, OwnedDirectory and exclusive
PrivateSinkFactory signatures/composition were checked and exercised with fake
remote I/O and real temporary host files. Source/config default performs no
device operations or output-directory creation. New capture root must separately
match the reviewed commit/blob/hash closure; old frozen runtime root is unchanged.

Current role bindings/boots/identity and fresh originals precede explicit setup.
Only planned ordinary native DBV/preferences/UI changes occur, not custom/raw
DSI, ESD isolation, selector writes or transaction/reboot watchdog. Such ordinary
setup can cause standard driver panel commands and is not described as no-write.
Restoration uses fresh captured originals, requires known same boot/stopped state,
and retains uncertainty when verification or navigation fails. Existing evidence
and media are not overwritten or deleted; only specifically owned UI files and
owned mutex are released after verified restoration.

Prior visual approval is provenance, not a claim that later PNG pixels were seen.
Dispatch rechecks native/software state, exact Settings component/focus/unlocked,
camera controls/progress, resumed camera ActivityRecord and MAIN/LAUNCHER Intent,
boots and mode-event continuity, and retains new private screenshots. Start must
occur within the same30s machine-gate interval. MAIN intent check rejects observed
VIDEO_CAPTURE/extras/pending intent overrides; absent pending-intent fields are
explicitly not proof of absence of all queued intents.

One Start is latched before dispatch, with no Stop toggle or automatic second
recording. Native10s cap is a preventive media limit with async/OEM residuals,
not an absolute OS wall guarantee. Start-to-verified-stop acceptance remains15s.
Unknown early controls make the result inconclusive, with no shifted windows or
qualifying PASS. V2 windows1–9s remain distinct from originalv1 and non-independent.

Private pull uses exact created inode, finite size/cap, source size/hash before
and after, sink lifecycle facts and local hash. Relevant explicit stat fields
are compared; neither launcher reads nor media hashing compares atime/full
os.stat_result tuples. Source/outcome/recording/before records bind the factual
analysis capsule; capsule requires verified stop, restoration and mutex release.
Encoded PTS and actual video geometry remain downstream requirements.

## Remaining non-code prerequisites

No fresh successful diagnostic receipt/visual evidence or actual UI/MAIN intent,
output route and hardware timing was obtained here. Source verification/tests
cannot establish those facts. Effective native duration must not be inferred
from a UI preference if a capture Intent could override it. Parent must honor
pending authorization/access restrictions and perform only the separately
permitted fresh readiness/deployment/execution. This review introduces no new
permission rule and overrides none of those restrictions.
