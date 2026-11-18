"""Read only tracked display evidence. No external processes, devices or media."""
import json
from math import isfinite
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
NODE = 'qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4'


def read(path):
    return json.loads((BASE / path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def scale_interval(time_us, separation_px, exposure_max_us):
    """Box-exposure midpoint ±E/2 per edge; total duration uncertainty ±E."""
    if any(x is None for x in (time_us, separation_px, exposure_max_us)):
        return None
    a, b = time_us
    c, d = separation_px
    require(all(isfinite(x) for x in (a,b,c,d,exposure_max_us))
            and 0 < a <= b and 0 < c <= d and exposure_max_us >= 0,
            'invalid timing or geometry')
    return [max(0, a-exposure_max_us)/d, (b+exposure_max_us)/c]


def selected(panels, name):
    rows = [p for p in panels if p['name'] == name]
    require(len(rows) == 1, 'selected node missing or duplicated')
    return rows[0]


def run():
    obs = read('post_ota_display_observation.json')['properties']['ro.build.display.id']
    require(obs['exit_code'] == 0, 'target build not observed')
    current = obs['stdout']
    inventory = read('device_tree/selected_boe_v4_acquisition.json')
    require(inventory['live_node'].split('/')[-1] == NODE, 'target panel mismatch')
    manifest = read('firmware_manifest.json')
    diff = read('regional_dtbo_diff.json')
    refs = {v['reference']: v for v in read('device_tree/selected_boe_v4_comparison.json')['references']}
    row = selected(diff['panels'], NODE)
    target = BASE/'device_tree/selected_boe_v4'
    live = {p.relative_to(target).as_posix() for p in target.rglob('*-command') if p.is_file()}
    require(len(live) == refs['cn']['shared_command_arrays'] == refs['eu']['shared_command_arrays'],
            'inconsistent command universe')
    rechecked = []
    for prop in row['changed_properties']:
        if not prop['property'].endswith('-command'):
            continue
        key = prop['relative_node'].strip('/') + '/' + prop['property']
        require(key in live, 'unexpected command path')
        value = (target/key).read_bytes()
        require(bytes.fromhex(prop['global']['raw_hex']) == value
                and bytes.fromhex(prop['cn']['raw_hex']) != value, 'byte cross-check failed')
        rechecked.append(key)
    require(len(rechecked) == len(set(rechecked))
            and set(rechecked) == {x['property'] for x in refs['cn']['changed_command_arrays']},
            'changed command set mismatch')
    cn48 = read('cn_48_7_recon_20261107/comparison.json')
    cn48_id = read('cn_48_7_recon_20261107/acquisition.json')
    require(cn48['selected_node'].split('/')[-1] == NODE and cn48['target_build'] == current
            and cn48['reference_build'] == cn48_id['build'] and len(cn48['commands']) == len(live)
            and {r['property'] for r in cn48['commands']} == live, 'CN48 comparison scope mismatch')
    rows = []
    for which, iddata, region in [('cn',manifest,'cn'), ('eu',manifest['global_reference'],'global')]:
        require(all(iddata[k] in diff['archives'][region] for k in ('model','region','build')),
                'reference version mismatch')
        ref = refs[which]
        require(ref['shared_command_arrays']-len(ref['changed_command_arrays']) == ref['equal_command_arrays'],
                'incorrect archived count')
        rows.append([iddata['model'],iddata['region'],iddata['build'],ref['equal_command_arrays']])
    rows.append([cn48_id['model'],cn48_id['region'],cn48_id['build'],sum(r['equal'] for r in cn48['commands'])])
    crop = read('night_r055_r057/results.json')['crop_example']
    cal = read('night_r052_r054/outcome.json')
    geom = read('night_r022_r024/outcome.json')['R024']
    require(cal['physical_time_unit'] is None and geom['selected_sensor_scenario'] is None
            and crop['unequal'] == 0, 're-evaluate physical scale assessment')
    return {'camera_reentry_pairs_scored':0,
            'physical_inputs':{'independent_optical_edge_interval_us':None,
                               'qualified_marker_separation_px':None,'effective_exposure_upper_us':None},
            'physical_us_per_px':scale_interval(None,None,None),
            'synthetic_indistinguishable_us_per_px':[v['modeled_us_per_px'] for v in crop['models']],
            'target_build':current,'target_node':NODE,'command_properties':len(live),
            'reference_rows_model_region_build_equal':rows,'bytes_rechecked_paths':sorted(rechecked),
            'excluded_nodes_with_number_of_changed_commands_vs_global':{
                p['name']:sum(x['property'].endswith('-command') for x in p['changed_properties'])
                for p in diff['panels'] if p['name'] != NODE},
            'physical_pwm_hz':None}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
