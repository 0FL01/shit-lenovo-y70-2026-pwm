# Historical Settings and fragment-section observation scope

Base: e9f7af5788c016b6bf60a724498e02ff29987dec. Offline source correction only.
No device operations, commit, push, candidate admission or physical qualification.

## Two independently reproduced parser defects

The saved baseline opened dump includes a stopped historical Settings home
activity, a stopped launcher, and the live ScreenTimeoutSettings destination.
The observer rejected the historical home solely because its component was not
one of the two calibrated destinations. Once that was corrected, Looper pending
transaction items named WindowStateInsetsControlChangeItem were incorrectly
counted as active fragments by a whole-activity regular expression. The live
support fragment section itself has one ScreenTimeoutSettings fragment.

## Narrow changes

Only `_available_settings_context` changes in the runtime. An uncalibrated
Settings component is excluded from scene consideration only with the exact
calibrated process/user/uid/display identity, a complete native stopped and
unfinished lifecycle, an added/unremoved stopped root, no focus, visibility 8,
and a created, stopped/nonresumed support manager with state 4, stopped true,
and destroyed false. Every required classification field must be present,
unique and well formed. Missing or contradictory classification data is terminal.
Historical fragment names and trees are not substituted into the live scene.

Active-fragment identity enumeration is scoped to the support manager section
before Added Fragments, matching the complete parser. Actual multiple active
fragments remain terminal. Missing support headers retain the conservative
whole-body validation fallback, so missing data cannot hide a contradiction.

The complete parser, live tree/digest, live configuration and identity checks,
settle loop, input ordering and deadline are unchanged. Unknown resumed/live
Settings components, conflicting historical classification, changed live
identity/configuration/tree, and ambiguous live activities remain failures.
No new live-tree normalization or synthetic readiness projection is used.

## Evidence and tests

Private exact replay derives both expected scenes from independent same-run
calibration captures and verifies their digests against the source-bound run
report. It verifies the failing observation's integrity separately. The
untouched failing dump now raises SettingsTransitionPending with the exact
opened calibration scene; it does not produce stable success.

The real redraw caller with fake I/O and repeated untouched pending observations
exhausts the original single 1-second acceptance budget, opens once, sends no
Back, and retains its pending latch. This replay passes normal and optimized
Python with explicit checks that remain enabled under -O. Raw dumps, identifiers,
and replay inputs remain private outside the repository.

Synthetic regressions cover stopped historical home plus live ready/opened,
ordering, pending versus stable results, multiple historical fragment names,
missing/duplicate/malformed classification fields, foreign identity, contradictory
lifecycle/root/support state, changes to live scene fields, and Looper transaction
items versus actual duplicate active support fragments. Scoped runtime and
consumer test results are recorded beside this review; unavailable historical
private fixtures are explicitly skipped, not treated as executed.

The host runtime pin and current runtime closure identify the changed bytes.
Independent revision2 review passed. A separately authorized full source-bound
stock trial remains necessary. This patch does not qualify AA10/P8514 or prove PWM frequency.

Results: 189 runtime/source tests per mode, 4 unavailable private-reference skips per mode; 84 consumer tests per mode, no skips. Independent exact current-run private replay passes both modes. AST comparison against base confirms no runtime changes outside the observer. git diff --check passes.


## Independent review correction: field ownership

The first revision searched historical classification fields across the activity
body. Independent review demonstrated that moving root mStopped into the support
area or moving manager mCurState before the support header incorrectly preserved
classification. Those malformed observations must never qualify as background.

The revised helper checks both whole-block uniqueness and presence in the owning
native/root/support/manager section. Unique boundary headers and their ordering
are mandatory. Root scope ends before the next same-indent section; support
lifecycle precedes active fragment records; manager state belongs after its own
header. The native Local Activity range retains its legitimate resources line.
Relocation tests cover native lifecycle, root added/removed/stopped/focus/visibility,
support lifecycle and manager tail, together with reordered manager/added headers.
All must fail terminally even beside an otherwise valid or incomplete live scene.
The exact untouched private replay remains pending-only in both Python modes.


## Independent revision2 review

The first draft was held because a relocated lifecycle field outside its owning
ViewRoot/support section could incorrectly classify historical evidence as
complete. Revision2 adds ordered section boundaries, field ownership and retained
whole-block duplicate rejection. Both exact reproducers now reject, as do 28
additional malformed-background/partial-live combinations. The independent
reviewer passed 85 tests in normal and optimized modes (three unavailable
historical fixtures skipped), plus the exact current-run replay in both modes.
No live-scene, input-policy or deadline change was needed. Reviewed runtime:
7cadad2b5b0cbe6908fbaaae8878599fb6ba9d64d264fe1eeb6c615813a677bd.
