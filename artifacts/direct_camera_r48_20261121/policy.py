#!/usr/bin/env python3
"""python3 -B policy.py ARCHIVE > policy.csv

One row per acquisition.log POINT TAG req=FLOAT bl=INT, in receipt order. Each
point must have its own .sf .display .top .session .bl .thermal .dc .pref
.wake. Compare only samples of one advancing BT709 player surface in one wake.
An invalid point aborts before CSV output; a partial sweep is still reportable.

req_sdr is the command argument, sdr_setting the framework setting, and the
Photonic Modulator's actual backlights are normalized framework values. A
clamp is reported only when the request exceeds the observed manual maximum
and applied brightness reaches it. sysfs_bl is an independent integer read.
Neither sysfs nor the frame counter measures panel DBV or optical output.
R36's native ceiling reads are a historical control, never an R48 readback.
"""

import argparse
import csv
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ARTIFACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACTS))
from direct_camera_r43_20261121.windows import original, require
from direct_camera_r44_20261121.windows import snapshot
from direct_camera_r46_20261121.windows import video_sample
from direct_camera_r47_20261121.policy import close, display_policy, receipts


def r36_control():
    # R36 result.md identifies the manual 1.0 request and applied 0.86662334.
    # Its published native receipts independently bind sysfs to 00:52 twice.
    path = ARTIFACTS / 'direct_camera_r36_20261120/readbacks.csv'
    with original(path).open(newline='') as f:
        peak = [r for r in csv.DictReader(f) if r['native_group'] == 'peak']
    require([r['side'] for r in peak] == ['pre', 'post'] and
            len({r['wake_epoch'] for r in peak}) == 1 and int(peak[0]['wake_epoch']) > 0 and
            all(int(r['DBV'], 16) == int(r['sysfs_bl']) == 14078 for r in peak),
            'R36: missing or inconsistent peak native control')
    return dict(r36_peak_req_sdr=1.0, r36_peak_applied_sdr=0.86662334,
                r36_peak_sysfs_bl=int(peak[0]['sysfs_bl']),
                r36_peak_dbv_pre_hex=peak[0]['DBV'], r36_peak_dbv_post_hex=peak[1]['DBV'])


def bind(archive):
    control = r36_control()
    epoch_file = archive / 'epoch'
    epoch = int(original(epoch_file).read_text()) if epoch_file.exists() else None
    rows = []
    previous = None
    for tag, req, bl in receipts(archive):
        def text(suffix):
            return original(archive / f'{tag}.{suffix}').read_text()

        try:
            if epoch is None:
                epoch = int(text('wake'))
            require(epoch > 0, 'invalid wake epoch')
            snap, seq = snapshot(archive, tag, 'sdr', bl, 0, 120, epoch, 'off')
            require(snap['hbm_mode'] == 'off', 'expected SDR with HBM off')
            sf = text('sf')
            surface, frame = video_sample(sf)
            require(surface.rsplit('#', 1)[1] == str(seq), 'physical surface identity mismatch')
            if previous:
                require(surface == previous[0] and frame > previous[1],
                        'surface changed or video frame counter did not advance')
            p = display_policy(sf, text('display'))
            require(p['brightness_reason'] == 'manual' and p['hbm_stats_state'] == 'HBM_OFF',
                    'expected unmodified manual brightness, HBM off')
            require(p['thermal_cap'] == 1 and not p['thermal_cap_applied'], 'thermal cap not normal')
            require(0 < bl <= p['sdm_max_bl'], 'BL outside current SDM range')
            actual, cap = p['fw_actual_sdr_backlight'], p['cached_max']
            require(close(actual, p['fw_actual_hdr_backlight']) and close(cap, p['hbm_current_max']) and
                    0 <= p['cached_min'] <= actual <= cap <= 1, 'inconsistent SDR backlight or ceiling')
        except (ValueError, OSError) as exc:
            raise ValueError(f'{tag}: {str(exc).removeprefix(tag + ": ")}') from None

        if close(req, actual):
            clamp = 'request_applied'
        elif req > cap and close(actual, cap):
            clamp = 'clamped_to_manual_max'
        else:
            clamp = 'request_differs_from_actual'
        # Only compare a new 1.0 command to the historic 1.0 control.
        ceiling_match = (clamp == 'clamped_to_manual_max' and close(actual, control['r36_peak_applied_sdr']) and
                         bl == control['r36_peak_sysfs_bl']) if req == 1.0 else None
        rows.append(dict(tag=tag, req_sdr=req, sdr_setting=p['sdr_setting'],
                         request_matches_setting=close(req, p['sdr_setting']),
                         cached_max=cap, hbm_current_max=p['hbm_current_max'],
                         fw_actual_sdr_backlight=actual, fw_actual_backlight=p['fw_actual_hdr_backlight'],
                         request_disposition=clamp, receipt_bl=bl, **snap, sdm_max_bl=p['sdm_max_bl'],
                         sysfs_delta_from_14056=bl - 14056,
                         brightness_reason=p['brightness_reason'], hbm_stats_state=p['hbm_stats_state'],
                         thermal_cap=p['thermal_cap'], thermal_cap_applied=p['thermal_cap_applied'],
                         surface_id=seq, video_frame=frame, frame_delta=frame-previous[1] if previous else None,
                         r48_panel_dbv_readback='not_in_point_snapshot', r48_optical_output='not_assessed_here',
                         **control, r36_ceiling_matches_at_req_1=ceiling_match))
        previous = surface, frame
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive', metavar='ARCHIVE', type=Path)
    args = ap.parse_args()
    try:
        rows = bind(args.archive)
    except (ValueError, OSError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
