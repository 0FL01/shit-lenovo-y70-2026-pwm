# Proposed causal split of the verified DC selector pair

Status: **completed, authorization consumed**. Owner: «Разрешаю, yolo»;
[exact authorization](authorization.json), [result](result.md). Each candidate
was applied once. No additional combination/repetition is implied.

## Question

The joint `23:A9/24:9D = 8E/8E` replacement previously suppressed the fine
optical component after redraw, with the broad component still present.
Which individual high-byte change is sufficient? This does not assume that
either field is a frequency divider or that the result will meet>=2000Hz.
The new readback method permits checking the requested field values directly.

## Exact scope

- Whole live875-byte/75-packet DC OFF program; headers, order, HS mode and
  all other payload bytes unchanged. [Offline validation](validation.json).
- `a9_only.bin`: packet6/page23:A9, raw byte68, `0E→8E`, native ON value.
  Page24:9D stays0E.
- `9d_only.bin`: packet9/page24:9D, raw byte97, `0E→8E`, native ON value.
  Page23:A9 stays0E.
- One pass: **stock →a9_only →stock →9d_only →stock**. Each variant once;
  no combination, alternate value, low-byte sweep or page4F modification.
- Each state: native table verification →sameDBV3600 →verified redraw →
  short readback of23:A9,24:9D andGET brightness52 →page0/ESD restoration →
  seven-second optical hold. Software120Hz, fixed Pacman100µs/ISO6400,
  AE/AF OFF, verified manual focus and stabilization OFF. Compare fine and
  broad structure, image signal and stock return; no Hz from pixel spacing.

## Execution and return

Reuse the proven bounded native transport and its module-hash, pending-buffer,
packet/order/HS, callback/driver-error, zero-miss and state guards. Keep short
reads under device-side timeout and independently verify ESD `reg_read`.
Stop on the first transport/readback/state error. Do not flush an uncertain
partial batch; ordinary reboot and verified persistent-root/stock-display
return are the recovery, as in the previously approved temporary trials.
After each candidate send the full original OFF table and redraw; verify
both high bytes back at0E. Restore captured policy/logger and remove own
temporary traces/files. No flash, module/DTBO/table replacement, AVB/slot,
security change or persistent profile. Camera remains ready as requested.

Nothing in this proposal identifies a high-frequency mode yet. It separates
the already causal mode-selection pair; a different byte or follow-on
combination is outside this exact scope.
