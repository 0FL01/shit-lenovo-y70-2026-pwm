#!/usr/bin/env python3
"""Build spec_round22_31.json for the R22-R31 night campaign.

All 139 phase frames are consumed in capture order (the runner pulled them
per phase; the ls order = chronological). Root-level baselines and steady
bursts are named explicitly.

Round map (sysfs 512 white unless noted; fresh dc-off snapshot restore before
every phase apply; camera A001 EXPERT 0.6x RAW ISO 6400 manual):
  R22 rig re-baseline + register page dumps (23/24 in DC and PWM; 4F/51/52/53/63 in DC)
  R23 9D low-nibble sweep 0x1e..0x7e + 0x8e ref
  R24 9D bit variants above 0x8e (0x9e/0xae/0xce/0xee/0x8f/0x8c/0x8a)
  R25 0x9e replication + sysfs sweep (256/1024/3600/6873) + 80=0x50; 0x8f family
  R26 9D ladder completion (0x80/82/84/88/90/92/94/98/a0/9c)
  R27 bit0 combos (0x81/83/85/91) + dimming probes on 0x92 (85=0x14, 95=1188, 4F:81=00/ff)
  R28 gray content (#404040/#202020/#101010) on 0x92/0x8e/0x9e
  R29 156us wave discrimination (pwm/8e/92/9e) + 0x9e steady burst at 156us
  R30 0x90 steady burst at 156us + PWM-state 9D=0x9e probe
  R31 0x92 and 0x9e steady bursts at 624us (residual-band rates)

Usage: gen_r2231_spec.py OUT_SPEC.json EV_R22_DIR FRAMES_DIR
"""
import json
import re
import sys
from pathlib import Path


def main(out_path: str, ev_dir: str, frames_dir: str) -> int:
    ev = Path(ev_dir)
    fr = Path(frames_dir)
    frames = sorted(p.name for p in fr.glob("IMG_*.DNG"))
    if len(frames) != 139:
        raise SystemExit(f"expected 139 phase frames, found {len(frames)}")

    def take(n: int) -> list:
        out = frames[:n]
        del frames[:n]
        return out

    phases: dict[str, list] = {
        # --- rig baselines (evidence root) ---
        "r22_flat_pwm6879": [
            "IMG_20260502_170254392.DNG", "IMG_20260502_170258744.DNG",
            "IMG_20260502_170303065.DNG"],
        "r22_pwm512_baseline": [
            "IMG_20260502_170349617.DNG", "IMG_20260502_170353961.DNG",
            "IMG_20260502_170358318.DNG", "IMG_20260502_170402658.DNG"],
    }
    order = [
        # R23 (4 frames each)
        ("r23_9d8e_ref", 4), ("r23_9d1e", 4), ("r23_9d2e", 4), ("r23_9d3e", 4),
        ("r23_9d4e", 4), ("r23_9d5e", 4), ("r23_9d6e", 4), ("r23_9d7e", 4),
        # R24 (3 each)
        ("r24_9d9e", 3), ("r24_9dae", 3), ("r24_9dce", 3), ("r24_9dee", 3),
        ("r24_9d8f", 3), ("r24_9d8c", 3), ("r24_9d8a", 3),
        # R25
        ("r25_9e_rep512", 4), ("r25_9e_bl256", 3), ("r25_9e_bl1024", 3),
        ("r25_9e_bl3600", 3), ("r25_9e_bl6873", 3), ("r25_9e_8050", 3),
        ("r25_8f_rep512", 3), ("r25_8f_8050", 3),
        # R26 (2 each)
        ("r26_9d80", 2), ("r26_9d82", 2), ("r26_9d84", 2), ("r26_9d88", 2),
        ("r26_9d90", 2), ("r26_9d92", 2), ("r26_9d94", 2), ("r26_9d98", 2),
        ("r26_9da0", 2), ("r26_9d9c", 2),
        # R27 (2 each)
        ("r27_9d81", 2), ("r27_9d83", 2), ("r27_9d85", 2), ("r27_9d91", 2),
        ("r27_92_8514", 2), ("r27_92_951188", 2), ("r27_92_4f8100", 2),
        ("r27_92_4f81ff", 2),
        # R28 gray content (2 each)
        ("r28_92_g64", 2), ("r28_8e_g64", 2), ("r28_92_g32", 2),
        ("r28_8e_g32", 2), ("r28_92_g16", 2), ("r28_9e_g16", 2),
        # R29 wave discrimination at 156us (2 each)
        ("r29_pwm_156", 2), ("r29_8e_156", 2), ("r29_92_156", 2), ("r29_9e_156", 2),
        # R30/R31 single runner frames
        ("r30_90_156_first", 1), ("r30_pwm9e", 2),
        ("r31_92_burst_first", 1), ("r31_9e_burst_first", 1),
    ]
    for name, n in order:
        phases[name] = take(n)
    if frames:
        raise SystemExit(f"unconsumed frames: {frames}")

    # steady bursts (evidence root)
    phases["r29_9e_156_burst_steady"] = [
        "IMG_20260502_174344019.DNG", "IMG_20260502_174348344.DNG",
        "IMG_20260502_174352694.DNG", "IMG_20260502_174357053.DNG",
        "IMG_20260502_174401393.DNG", "IMG_20260502_174405731.DNG"]
    phases["r30_90_156_burst_steady"] = [
        "IMG_20260502_174540975.DNG", "IMG_20260502_174545342.DNG",
        "IMG_20260502_174549672.DNG", "IMG_20260502_174554013.DNG"]
    phases["r31_92_624_burst_steady"] = [
        "IMG_20260502_174811608.DNG", "IMG_20260502_174815763.DNG",
        "IMG_20260502_174819899.DNG", "IMG_20260502_174824027.DNG",
        "IMG_20260502_174828179.DNG", "IMG_20260502_174832308.DNG",
        "IMG_20260502_174836436.DNG", "IMG_20260502_174840623.DNG"]
    phases["r31_9e_624_burst_steady"] = [
        "IMG_20260502_175004830.DNG", "IMG_20260502_175008996.DNG",
        "IMG_20260502_175013114.DNG", "IMG_20260502_175017261.DNG",
        "IMG_20260502_175021390.DNG", "IMG_20260502_175025541.DNG",
        "IMG_20260502_175029697.DNG", "IMG_20260502_175033824.DNG"]

    # register readbacks from the saved runner outputs
    rb = {}
    for pf in sorted(ev.glob("r22_*_apply.txt")) + sorted(ev.glob("r22_pwm_entry_ret.txt")):
        fields = {}
        for line in pf.read_text().splitlines():
            m = re.match(r"^RD (\S+) (0x[0-9A-Fa-f]+) (.+?)\s*$", line)
            if m:
                fields[f"{m.group(1)}:{m.group(2)[2:].upper()}"] = m.group(3).replace("0x", "")
        if fields:
            rb[pf.stem] = fields

    spec = {
        "experiment": "ddic_round22_31_9dladder_20261120",
        "panel": "BOE ILI97701A cmd_v4 (ID 0xd2)",
        "reference_dng": "IMG_20260502_170254392.DNG",
        "b2_roi": [500, 590, 580, 660],
        "narrow_col_slice": [610, 620],
        "target_wave_vector_k": [2, 0],
        "fixed_conditions": {
            "camera": "A001 Camera ID 2 (EXPERT 0.6x RAW, 3264x2448), ISO 6400 manual",
            "exposure_note": (
                "nominal 1/1600 step: dumpsys 624000 ns, DNG tag 624 us; the day "
                "campaign recorded 625 us for the same nominal step; 156 us phases "
                "are listed in phase_exposure_us"),
            "refresh_hz": 120,
            "pattern": ("#FFFFFF via HTMLViewer data:text/html base64 URI; gray phases "
                        "r28_* use rgb(64/32/16)"),
            "esd_check_mode_restored": "reg_read",
            "rig_note": (
                "owner re-assembled the bench: the white field no longer covers the "
                "day ROI (raw y90-270, x1860-2020); this campaign is internally "
                "re-based on a new ROI inside tonight's white core with a new "
                "reference flat; cross-references to R9-R21 are qualitative only"),
            "entry_note": ("every phase entered from the full dc-off snapshot restore "
                           "(r9_ret.cmd) before its apply; steady bursts were shot "
                           "~10 s after the apply to skip the landing transient"),
        },
        "phase_exposure_us": {
            "r29_pwm_156": 156, "r29_8e_156": 156, "r29_92_156": 156,
            "r29_9e_156": 156, "r29_9e_156_burst_steady": 156,
            "r30_90_156_first": 156, "r30_90_156_burst_steady": 156,
        },
        "ddic_readbacks": rb,
        "phases": phases,
    }
    Path(out_path).write_text(json.dumps(spec, indent=2) + "\n")
    n = sum(len(v) for v in phases.values())
    print(f"wrote {out_path}: {len(phases)} phases, {n} frames")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: gen_r2231_spec.py OUT_SPEC.json EV_R22_DIR FRAMES_DIR")
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
