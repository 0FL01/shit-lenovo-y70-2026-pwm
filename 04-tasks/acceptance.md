# Checkpoints and quality bar

## Stage 0: no hardware access

T02/T03/T04/T05/T07 can progress independently. Save source versions, diff reports, exact CLI, scripts and open questions. Do **not** block on T01 if device is temporarily disconnected.

## Stage 1: phone available, read-only

T01/T06/T08/T09. Confirm build, exact panel identity, bootchain and measurement. If runtime observations contradict online reviews, trust the phone and the optical measurement, then document the contradiction.

## Stage 2: feasibility decision

T10. Evidence can justify `GO: patch design`, `NO-GO: native PWM not tunable`, or `BLOCKED: proprietary controller documentation absent`.

## Stage 3: implementation and offline tests

T11. Do not confuse source compile success with flash readiness. Reproduce stock image first (when possible), compare boot header, modules and KMI; only then build changed image. Prefer isolated compile and tests before dangerous experiments. Deliver final diff; record hashes for images proposed for boot/flash and recovery, not for all reports and build outputs.

## Stage 4: optional hardware trial (separate stage)

T12 yields a proposal; the exact write operation is confirmed by the owner as a separate step after recovery plan and risk review. An optical before/after trace with successful rollback is required for validated «PWM uplift» claim.

## Required report distinctions

`PASS` means a verifiable observation. `LIKELY` means an evidence-based inference. `UNKNOWN` means data not available. `BLOCKED` means further progress requires missing access/docs. Inferred source strings are not promoted to a proven DSI register map without direct evidence.
