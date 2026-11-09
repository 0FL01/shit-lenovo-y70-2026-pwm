from fixtures import fixture_gate
"""Execute only explicit fake fixtures and print their journals as JSON."""
import json
from harness import Blocked, joint_result
from fixtures import setup, finish_target, finish_camera


def run_all():
    reports = []
    for name in ('both_fake_verified', 'target_verified_camera_callback_only',
                 'target_reboot_unknown_camera_verified', 'camera_session_replaced'):
        target, route, _ = setup('target')
        camera, _, _ = setup('camera')
        if name == 'target_reboot_unknown_camera_verified':
            fixture_gate(target).backend.script[1]['status'] = 'unknown'
        if name == 'target_verified_camera_callback_only':
            fixture_gate(camera).backend.script[2]['payload'].update(cap_callback_observed=True,
                                                          recording_active=True, stop_observed=False)
        if name == 'camera_session_replaced':
            fixture_gate(camera).backend.script[1]['guard']['session_id'] = 'foreign-session'
        for operation in (lambda: finish_target(target, route), lambda: finish_camera(camera)):
            try: operation()
            except Blocked: pass
        report = joint_result(target, camera)
        report['scenario'] = name
        report['fake_journals'] = {'target': fixture_gate(target).backend.log, 'camera': fixture_gate(camera).backend.log}
        reports.append(report)
    return {'kind': 'executed_fake_harness_results', 'physical_calls': 0, 'scenarios': reports}


if __name__ == '__main__':
    print(json.dumps(run_all(), indent=2))
