from weakref import WeakKeyDictionary
_fixture_gates = WeakKeyDictionary()
def fixture_gate(controller):
    """Test-only handle for injected fake results and internal adversarial probes."""
    return _fixture_gates[controller]

"""Explicit synthetic evidence; no claim that any physical reader is qualified."""
from copy import deepcopy
from dataclasses import replace
from custody_bridge import model as m, CustodyAdmission
from harness import FakeBackend, RecoveryGate, TargetRecovery, CameraRecovery

OLD = '00000000-0000-4000-8000-000000000001'
NEW = '00000000-0000-4000-8000-000000000002'
CAMBOOT = '00000000-0000-4000-8000-000000000003'
FAILED = {'status': 'failed', 'dispatch_uncertain': True, 'old_adapter': 'terminal'}
TARGET_ID = {'model': 'XT2611-1', 'module': 'fixture-exact-module', 'panel': 'fixture-exact-panel'}
CAMERA_ID = {'model': 'A001', 'package': 'net.sourceforge.opencamera', 'version': 'fixture-unmatched-binary'}
TARGET_SETTINGS = {'screen_brightness_mode': 0, 'screen_brightness': 123,
                   'screen_off_timeout': 60000, 'native_dbv': 1234, 'logger': 0}
PROFILE = {'exposure_ns': 100000, 'iso': 6400, 'focus_diopters': 2.0,
           'ae_lock': False, 'awb_lock': False, 'zoom': 1.0, 'camera_id': '0',
           'resolution': [1280, 720], 'fps': 30, 'audio': False}
CAMSETTINGS = {'video_mode': True, 'restart_count': 0, 'saf': False,
               'duration_limit': 0, 'size_limit': 0}


class Clock:
    now = 100
    def __call__(self): return self.now


class RouteFixture:
    def __init__(self, component, boot):
        self.component, self.boot = component, boot
        self.mutate = lambda c, e, t: (c, e, t)

    def __call__(self, binding, now):
        source = 'a'*64
        hops, qualifications, observations, clocks = [], [], [], []
        for index, hop in enumerate(m.Hop):
            domain = m.Domain('fixture-host-'+str(index), 'fixture-host-boot-'+str(index), 'monotonic_ns')
            end = int(now*1_000_000_000)+index*10000
            start = end-100
            expected = m.Binding(source, domain.boot, 'held-task-'+str(index),
                'fixture-exec-'+str(index), 'independent-held-channel-'+str(index),
                'fixture-ns-'+str(index), 'fixture-ssh', 'fixture-server-epoch',
                'fixture-transport', binding['device'], self.boot)
            hops.append(m.HopContract(hop, domain, start, expected))
            caps = [m.Capability.PIDFD_LIVE, m.Capability.EXE_SNAPSHOT,
                    m.Capability.HOLDER_SNAPSHOT, m.Capability.HELD_CHANNEL,
                    m.Capability.CUSTODY_CONTINUITY, m.Capability.EXEC_CONTINUITY]
            if hop is m.Hop.SSH_SESSION: caps.append(m.Capability.SSH_AUTH)
            if hop is m.Hop.TRANSPORT_DEVICE:
                caps += [m.Capability.PHYSICAL_SNAPSHOT, m.Capability.TRANSPORT_BINDING_SNAPSHOT,
                         m.Capability.TRANSPORT_PHYSICAL_CONTINUITY]
            reader = 'synthetic-reader-'+str(index)
            qualifications.append(m.Qualification(reader, 'b'*64, 'synthetic-qualification', hop, domain, frozenset(caps)))
            for seq, cap in enumerate(caps, 1):
                observations.append(m.Observation(hop=hop, domain=domain, start_ns=start,
                    end_ns=end, binding=expected, capability=cap, reader_id=reader,
                    reader_source_digest='b'*64, qualification_id='synthetic-qualification',
                    capture_digest=f'{seq:064x}', sequence=seq,
                    evidence_nonce=binding['operation_id']+'-evidence'))
            clocks.append((domain, end))
        contract = m.RouteContract(binding['incident'], binding['route'], source,
            m.Component(self.component), binding['device'], self.boot, 'synthetic-independent-review',
            binding['operation_id']+'-evidence', tuple(hops), tuple(qualifications), 100)
        return self.mutate(contract, tuple(observations), tuple(clocks))


def read(payload):
    return {'action': 'READ_STATUS', 'status': 'ok', 'observed_at': 100, 'payload': deepcopy(payload)}


def ack(action, status='ok'):
    guard = {'expected_boot': OLD if action == 'REBOOT_TARGET' else NEW}
    if action in ('STOP_CAMERA', 'RESTORE_CAMERA'):
        guard = dict(expected_boot=CAMBOOT, session_id='owned-recording-epoch', owner='fixture-owner',
                     recording_active=action == 'STOP_CAMERA')
    return {'action': action, 'status': status, 'guard': guard}


def target_data(boot):
    return {'physical_id': 'fixture-target', 'boot_id': boot, 'identity': deepcopy(TARGET_ID),
            'root_uid': 0, 'selinux': 'Enforcing', 'boot_completed': True,
            'dc_stock_safe': True, 'esd': 'reg_read', 'power_verified': True,
            'original_snapshot': deepcopy(TARGET_SETTINGS), 'settings': deepcopy(TARGET_SETTINGS)}


def camera_data():
    return {'physical_id': 'fixture-camera', 'boot_id': CAMBOOT, 'identity': deepcopy(CAMERA_ID),
            'session_id': 'owned-recording-epoch', 'owner': 'fixture-owner',
            'session_binding_verified': True, 'recording_active': False,
            'stop_only_capability_verified': True, 'stop_observed': True,
            'cap_callback_observed': False, 'media_id': 'fixture-original-media',
            'finalized': True, 'original_retained': True, 'decode_valid': True,
            'metadata_retained': True, 'activity': 'original-A-instance', 'task': 'original-A-task',
            'idle_preview_verified': True, 'profile': deepcopy(PROFILE), 'settings': deepcopy(CAMSETTINGS)}


def setup(component, script=None, *, incident_cause=None, authority=None, gate_route=None):
    boot = OLD if component == 'target' else CAMBOOT
    route, clock = RouteFixture(component, boot), Clock()
    state = m.RecoveryState('fixture-incident', 'a'*64, 'failed-old-route', True, True, OLD,
                incident_cause or m.IncidentCause.VERIFIED_NONSERVER_EXIT, 'synthetic-independent-incident-explanation')
    admission = CustodyAdmission(state, route, authority or (lambda r: m.Authority(r, 'synthetic-recovery-approval')))
    if script is None:
        if component == 'target':
            script = [read(target_data(OLD)), ack('REBOOT_TARGET'), read(target_data(NEW)),
                      ack('RESTORE_TARGET'), read(target_data(NEW))]
        else:
            pre = camera_data(); pre['recording_active'] = True
            script = [read(pre), ack('STOP_CAMERA'), read(camera_data()), read(camera_data()),
                      ack('RESTORE_CAMERA'), read(camera_data())]
    backend = FakeBackend(script)
    gate = RecoveryGate(component=component, incident='fixture-incident', route=gate_route or 'independent-route-'+component,
                        device='fixture-'+component, admission=admission, backend=backend, clock=clock)
    if component == 'target':
        controller = TargetRecovery(gate, FAILED, identity=TARGET_ID, old_boot=OLD, original_settings=TARGET_SETTINGS)
    else:
        controller = CameraRecovery(gate, FAILED, identity=CAMERA_ID, boot=CAMBOOT,
            session='owned-recording-epoch', owner='fixture-owner', media_id='fixture-original-media',
            original_activity='original-A-instance', original_task='original-A-task',
            original_profile=PROFILE, original_settings=CAMSETTINGS)
    _fixture_gates[controller] = gate
    return controller, route, clock


def finish_target(controller, route):
    controller.precheck(); controller.reboot()
    route.boot = NEW  # independent fixture observation, never inferred from reboot acknowledgement
    controller.changed_boot(); controller.restore(); controller.restored()


def finish_camera(controller):
    controller.precheck(); controller.stop(); controller.stopped()
    controller.finalized(); controller.restore(); controller.restored()
