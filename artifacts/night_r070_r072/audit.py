"""Offline joins of archived JSON; optional two-file verification of stock assets."""
import argparse
import hashlib
import json
import math
from pathlib import Path

A = Path(__file__).resolve().parents[1]
PANEL = 'mipi_mot_cmd_boe_1440p_dsc_682'
NODE = 'qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4'
ASSET = 'qdcm_calib_data_' + PANEL + '.json'


def read(name):
    return json.loads((A / name).read_text())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def asset_join(inv, r8, node, panel):
    cfg = r8['cn_qdcm']
    require(node == NODE and panel == cfg['panel'] == PANEL, 'wrong panel')
    rows = [x for x in inv['target_files']['files'] if x['path'] == '/vendor/etc/display/' + ASSET]
    require(len(rows) == 1 and rows[0]['sha256'] == cfg['sha256']
            and rows[0]['size_bytes'] == cfg['bytes'], 'historical file not bound to CN asset')
    profiles = cfg['profiles']
    enabled, disabled = [], []
    for name, row in sorted(profiles.items()):
        d = row['PostBlendDither']
        require(row['PostBlendPaDither']['enable'] == 0 and d['displayID'] == 0, 'different feature route')
        if d['enable'] is True:
            require(d['temporalEnable'] == 0 and d['ditherMode'] == 'LUMA', 'non-spatial enabled asset')
            enabled.append(name)
        elif d['enable'] is False:
            disabled.append(name)
        else:
            raise ValueError('missing boolean enable')
    require(len(profiles) == 12 and enabled == ['hdr-nature','hdr-vivid-300'], 'profile corpus changed')
    return dict(target_inventory_utc=inv['collection']['last_batch_at_utc'],
                historical_global_build=inv['build']['pre_ota_2026_10_28']['display_id'],
                selected_global_node=node, calibration_key=panel, whole_file_sha256=rows[0]['sha256'],
                spatial_only_enabled=enabled, disabled_profiles=disabled, current_merged_profile=None)


def refresh_row(i, phase, stage, native):
    require(i == phase['index'] == stage['phase'] == native['phase'], 'phase identity')
    req, actual = phase['requested_refresh'], phase['software_refresh_end']
    require(req == stage['requested_refresh'] and math.isfinite(actual)
            and abs(req - actual) < .02, 'not admitted: active SF mode absent or different')
    require(phase['dbv'] == 3600 and phase['dc'] == 0 and phase['redraw_completed'] is True
            and native['hold_write_packets'] == 0 and stage['frames'] == 75, 'phase controls')
    return dict(phase=i, request=req, active_sf_peak_hz=actual,
                strongest_peak_rows=round(stage['peaks'][0]['period_rows'],3))


def audit():
    dt = A / 'device_tree/selected_boe_v4'
    dtstr = lambda k: (dt/k).read_bytes().rstrip(b'\0').decode()
    cfg = asset_join(read('device_inventory.json'),read('r8_stock_apl_dither_20261118/result.json'),
                     dtstr('name'),dtstr('qcom,mdss-dsi-panel-name'))
    run = read('stock_base_rates_20261107/run.json')
    analysis = read('stock_base_rates_20261107/analysis.json')
    native = analysis['native']
    p, s, n = run['phases'], analysis['stages'], native['phases']
    require(len(p) == len(s) == len(n) == 5, 'incomplete sweep')
    rows = [refresh_row(i,*args) for i,args in enumerate(zip(p,s,n),1)]
    require([r['request'] for r in rows] == [120,144,120,90,120] and run['target_restored']
            and not run['cleanup_errors'], 'return not bound')
    counts = {k:native[k] for k in ['timing_packets','controller_returns','negative_returns','probe_misses']}
    require(list(counts.values()) == [62,85,0,0], 'native summary changed')
    snapshots = read('STOCK_EXTRA_DIM_20261118_data.json')['target_snapshots']
    keys = ('transaction_pre','on1_pre','restore_independent','final')
    fields = [snapshots[k]['fields'] for k in keys]
    require(fields[0] == fields[2] == fields[3], 'software restore absent')
    rgb = []
    for f in fields:
        m = f['color_matrix']
        require(f['panel_brightness'] == 828 and f['vsync_hz'] == 120.0 and f['active_sf_mode'] == 0
                and f['panel_dc'] == 0 and f['hdr_layer'] == 'false', 'extra dim controls')
        require(m[0][0] == m[1][1] == m[2][2], 'unequal RGB gains')
        rgb.append(m[0][0])
    require(rgb == [1,.522,1,1], 'missing contrast')
    return {'R070':cfg,'R071':{'sweep':rows,'native_archive_counts':counts,'independent_sweeps':1},
            'R072':{'extra_dim_snapshot_rgb_diagonal':rgb,'active_sf_mode':0,'panel_brightness':828},
            'new_device_actions':0,'physical_pwm_hz':None}


def check_assets(paths,expected):
    for p in paths:
        require(p.name == ASSET and hashlib.sha256(p.read_bytes()).hexdigest() == expected, 'asset mismatch')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-files', nargs=2, type=Path, metavar=('CN', 'RETEU'))
    args = ap.parse_args()
    result = audit()
    if args.stock_files:
        check_assets(args.stock_files,result['R070']['whole_file_sha256'])
    print(json.dumps(result, indent=2, sort_keys=True))
