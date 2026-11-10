# Selector ESD observation boundary

Status: offline source-supported correction; independent implementation review
pending. Actual saved0171 cause remains unknown. That capture was not obtained
or read for this correction. No device operation, deployment, Git publication,
WORKSTATE write, or new physical qualification is included.

## Evidence and scope

Before this change selector CHILD restored reg_read before the enclosing
TRACE_AFTER. In a synthetic generated-shell experiment, one rc1 control return
inserted after ESD_RESTORED left all ten local gates and shell rc0 successful,
while the unchanged host validator rejected Unexpected callback/control delta.
That demonstrates a possible observation-boundary exposure, not attribution of
the actual run failure, and does not justify accepting an extra return.

The selector now checks mode5 again after its final local gate and emits exactly
ESD_HELD esd_sw_sim_success. Legacy restored-child framing is rejected. It does
not restore reg_read in CHILD, traps or finally blocks. The host completes the
existing envelope ownership, prechild trace guard, before/after trace, state and
boot checks, exact seven page callbacks, exact ten controller returns, selector
values and native interval validation before attempting restoration.

The validated entry count and exact TRACE_AFTER cursor are saved before the
separate verified restoration. This preserves resumed native polling for the
next existing safe-gap guard. No post-restore reread replaces that cursor. The
existing writer_esd_script restore path supplies ownership, mode5 precondition,
LF write, reg_read readback and exact restoration marker; mutation=True preserves
the in-flight latch. pending_read clears only after success. Caller-owned
panel_uncertain is never cleared by selectors(). Errors, uncertain completion,
late responses and wrong markers still require the existing reboot recovery.

The new aa_selector_esd_isolation_v1 lifecycle contract is required by runtime,
acquisition validation and stock qualification. Host validation/restoration
monotonic times are finite, ordered and constrained to their acquisition phase.
They are not invented device isolation times. This does not cancel an already
in-flight ESD check: any extra or changed event inside the outer operation remains
terminal. No controller whitelist, dropped suffix or weakened trace/wire/native
check is introduced.

## Timing and limitations

Restoration replaces the prior post-selector read-only ESD dispatch, so there is
no added host dispatch or fixed quiet wait. Mount/write/readback overhead and
physical end-to-end latency are unknown. Limits remain 37/45/8/60/600 seconds,
nonrenewed watchdogs and the existing camera/identity/recovery gates. A fresh
same-source stock composition is still required before candidate admission;
this patch does not authorize a physical retry or establish optical/DDIC recovery.
AA readplane semantics and physical PWM Hz remain unknown.

## Verification

Tests use synthetic operation and host transports, plus only previously
authorized external scene references for existing regressions. No private raw
fixture is stored here. The dedicated selector suite covers generated final
mode readback failures, no child restore, legacy framing rejection, unowned
prefix/suffix controls, cursor retention, caller latch ownership, envelope/native
faults, real inherited shell and deadline transport restoration failures,
reboot-only full-run failure paths, lifecycle consumers and unchanged size caps.
Existing source-profile tests additionally require the exact selector contract
and reject coherently reidentified tampered runtime bytes against reviewed pins.

Author verification: 165 runtime/source tests pass in normal and optimized
Python with zero skips. The explicitly named four-module optical/acquisition
regression set passes 84 tests in both modes. Final command sizes and source
identities are in the runtime closure; independent review remains pending.
Earlier historical closure sections describe their own revisions and are not
qualification of this one.
