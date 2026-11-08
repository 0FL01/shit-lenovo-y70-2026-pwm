# Proposal: read-only ILI97701A register dump — 2026-11-07

Goal: obtain the real DDIC register map (including OTP-loaded values never written
by DT) to locate an EM pulse-count / PWM-period field. Stock ~720 Hz (`hypothesis`:
6 pulses × 120 Hz; camera estimate 680–720 Hz from skew 15.05 ms, 93.5-row period).

Mechanism (`confirmed-on-target` presence, 2026-11-07): msm_drm debugfs
`dri/9800000.qcom,mdss_mdp/DSI-1/rx_cmd` + `tx_cmd`; ESD node
`qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode` = `reg_read`.

Exact DSI traffic per register (tools: `06-tools/ddic_regdump.sh`, `run_ddic_regdump.py`):
1. `39 … 04 FF 5A A5 <page>` (page selector; same form stock sends)
2. DCS read `06 01 00 01 00 00 01 <reg>`, length 1 (probe: up to 30)
3. `39 … 04 FF 5A A5 00` immediately
No other register writes. ESD set to `esd_sw_sim_success` during dump, restored to
`reg_read` by trap and verified afterwards. Manual brightness + fixed refresh to avoid
kernel `51` writes / LTPO switches while a non-zero page is selected.

Stages (each stops on failure):
- S0 probe: 18 multi-byte reads; continue only if ground-truth values from DT match.
- S1 known pages ×256 regs ×2 passes, brightness 52 (DBV3584), 120 Hz.
- S2 same at 53 (DBV3646, above 3601 threshold).
- S3/S4 same at 52 with 144 Hz and 60 Hz.
- S5 census pages 00–7F × 256, one pass, 52/120 Hz.

Risk: reads only; worst realistic case is a mis-sequenced page causing an ESD-style
panel re-init or a visual glitch, cleared by screen off/on or reboot. No persistence,
no image/partition writes. Settings restored to originals, screen off at end.
