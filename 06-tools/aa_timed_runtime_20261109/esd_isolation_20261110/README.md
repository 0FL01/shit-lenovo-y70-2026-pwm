# AA full-table ESD isolation correction

Status: offline implementation and fault tests passed. No physical trial,
deployment, commit or push was performed by this source worker. The worktree
is not admitted for live I/O. The next control remains stock-only; AA10 and
P85/14 are not admitted by this correction.

## Evidence and bounded purpose

The stock-only run at commit 65b1139 failed after three deferred chunks. The
saved 0096 envelope is exactly 5,930 bytes, SHA256
`3833a0220298d9f913c8686d7f1189d2da5eb58abcff04343f99ce29d2b17e21`.
Its CHILD status is 51. One native ESD controller return with rc=1 appears
between BLOCK 1 and BLOCK 2. The shared AWK and host transaction validator
correctly rejected it. BLOCK 3, BLOCK 4 and the 75-packet flush never occurred.
The original cache evidence is unchanged. The patch contains only a generated
synthetic counterexample and an optional external-cache reader. On nc-lab the
reader tests the exact saved bytes without copying raw traces into the repository.

Exact-module analysis shows that `esd_sw_sim_success\n` selects mode 5,
preventing hardware work in later ESD checks. The setter does not take the
checker's mutex or drain an older check. An older checker can therefore still
finish after isolation. Two seconds is a bounded observation period, not proof
of synchronous cancellation or a universal exclusion barrier.

## Implemented lifecycle

1. Latch uncertainty before any ESD mode mutation. In a private mount namespace,
   verify ownership and the existing normalized `reg_read` readback, write the
   exact LF-terminated `esd_sw_sim_success` token, and verify the normalized mode.
   The normalization remains the established NUL removal and shell trailing-LF
   handling; this does not assert a new raw debugfs byte format. Read errors are
   tested separately from token comparison.
2. Run the existing real two-second quiet interval after successful isolation.
   No sleep is added. Its native/state/kernel timestamp checks are unchanged.
3. Keep the parent trace active. The writer rechecks mode 5 before its initial
   snapshot and first dd. Existing ownership, source-bound chunks, PRE_GUARD,
   TRACE_GUARD, initial callback accounting and trace-prefix guards remain.
4. Keep mode 5 through all five blocks, final BLOCK 4, TRACE_AFTER, END, kernel
   dump, state evidence and host validation. BLOCK 4 must still equal TRACE_AFTER.
   Both wire intervals must still contain exactly 75 expected packets, and the
   shared per-block AWK still rejects every extra controller event. No ESD event
   is newly whitelisted inside the writer.
5. Only after complete authoritative validation, replace the former independent
   writer-esd read with the fixed `reg_read\n` transition and verified readback.
   Leave the isolated TRACE_AFTER as the cursor. A later known ESD completion is
   evaluated only by the existing safe-gap policy before the next operation.

Every isolation, readback, quiet, write, validation or restoration uncertainty
remains sticky and goes through existing same-target reboot recovery. Neither
helper nor writer restores ESD in an error trap. The trap only unmounts. Caught
errors also block later replay, selectors, C1, prehold and hold entrypoints.
There is no extra page return, DSI read, retry or table continuation on failure.
Operational recovery does not establish physical DDIC or optical recovery.

The fixed 875 bytes, 75 packets and five chunk boundaries are unchanged. Existing
fast-scene v2, selectors, replay and 37/45/8/60/600-second constraints are unchanged.
Isolation, quiet, table validation and successful restoration all count in
`writer_and_quiet`. The new acquisition lifecycle records their ordering. A
fresh same-source stock measurement is still required; no prior time is subtracted.

## Verification

Full suite: 125 tests passed with normal Python and 125 with `python3 -O`, with
zero skips in both final runs. Logs are adjacent to this file. The earlier
63-test exploratory run skipped the external scene pair. The first wider run
rejected a legacy synthetic video fixture missing lifecycle evidence; only that
synthetic fixture's host timing was corrected, preserving its camera timeline.
Those earlier runs are not the final PASS evidence.

The final suite includes:
- Real generated helper shell with fake mounts/files: exact LF bytes, ignored or
  failed writes, wrong/failed readbacks, read failures that emit the correct token,
  unmount failure, and no trap restoration.
- Real generated writer shell: mode mismatch before any dd, incomplete prior
  callbacks, and an extra controller event at each of the five block boundaries.
- Full runtime with real native/wire/framing/state validators and fake I/O:
  isolation/quiet/restore failures, late trace or kernel activity, wrong boot/state,
  no later child after a caught error, and exact successful lifecycle boundaries.
- The exact saved 65b1139 failure: envelope rejection, incomplete batch rejection
  and actual generated AWK statuses `[0, 0, 0, 51]`. A diagnostic event-removal
  comparison is not accepted evidence or permission to ignore the event.
- The actual pinned stable/pending Settings pair through the existing real parser
  and redraw caller; the fast-scene contract remains v2.
- Fixed-source imports/pins, deferred finalizer routing/tampering, inherited setup,
  acquisition/video validation and the unchanged loader suite.

Precommit positive source-profile tests use real source bytes with explicit fake
Git provenance. Separately, the real Git loader and post-load source gate both
reject this uncommitted worktree, as recorded in `source_gate_checks.json`.
No postcommit source-clean PASS is claimed; that requires the later reviewed
commit and a fresh check by the lead/operator.

The conservative command construction fixture uses a 100-character work basename,
128-character token, 180-character markers and six-digit prior trace counters.
Service bytes: stock 47,875; AA10 47,840; selectors 44,547; C1 35,518; ESD isolate
3,025; ESD restore 3,005. All are below the unchanged 65,535 service-byte and
131,072 argv-byte limits. This is offline construction evidence, not a physical
latency guarantee. The new isolation uses one additional shell call per table;
restoration replaces the previous writer-esd read call.

Run from the repository with both `06-tools` and
`06-tools/host_source_integration_20261109` on PYTHONPATH. Set the external pair
paths recorded in `SOURCE_FREEZE.json`. The eight test modules are recorded there
and in the closure manifest. Repeat the same command with and without `-O`.
