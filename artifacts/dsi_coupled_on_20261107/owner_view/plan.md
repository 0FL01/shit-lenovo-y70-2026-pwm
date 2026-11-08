# Owner-requested temporary S0C1 viewing

The owner stopped analysis and explicitly requested the already specified S0C1
profile for direct inspection. This is a separate manual-view operation, not reuse
of the consumed three-stage video authorization. Exact bytes/hash and uncertain-
queue recovery remain as in the parent proposal. No new composed panel values.

`python3 06-tools/run_dsi_mode_trial.py TARGET_TRANSPORT 0 --coupled-on-view`
checks identity/root/module/stock software policy, sends stock then S0C1 with the
same DBV3600/redraw/readback/native guards, and removes ESD simulation, logger,
probes and temporary device files. It intentionally leaves S0C1 and the temporary
manual52/requested120/DBV3600/10min-timeout policy active. No camera calls occur;
the zero camera argument is an unused placeholder. No `series_complete` or
`target_restored` success is claimed for an active handoff. Stop if uncomfortable.

On the owner's return request, re-identify the transport and execute:
`python3 06-tools/run_dsi_mode_trial.py TARGET_TRANSPORT 0 --coupled-on-return`.
This sends only the full stock program, replays DBV/redraw, verifies readback and
restores the original policy/native DBV saved in this manual session's `run.json`.
It refuses an uncertain queue; ordinary reboot is the already agreed recovery.
Successful return is recorded separately under `return/run.json`.

Do not change brightness, flicker-prevention, refresh policy or suspend the screen
while comparing this exact state: those can change/reset the panel state. There
is no auto-application after reboot. The owner can inspect now and ask for stock;
no improvement, pulse frequency or comfort result is presumed before that response.
