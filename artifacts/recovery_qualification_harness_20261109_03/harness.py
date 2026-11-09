from readonly import ReadOnly
"""Pure recovery state machines. Literal fake backend only; never physical dispatch."""
from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from uuid import UUID
import json

ACTIONS = {'READ_STATUS', 'REBOOT_TARGET', 'RESTORE_TARGET', 'STOP_CAMERA', 'RESTORE_CAMERA'}


class Blocked(ValueError):
    pass


def exact(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


class FakeBackend:
    """Consumes predeclared results; it cannot interpret or execute a command."""
    def __init__(self, script):
        self.script = deepcopy(script)
        self.log = []

    def dispatch(self, action, payload):
        if action not in ACTIONS:
            raise Blocked('action outside finite recovery vocabulary')
        entry = {'action': action, 'payload': deepcopy(payload), 'physical': False, 'effect_applied': False}
        self.log.append(entry)
        if not self.script:
            return {'status': 'unknown'}
        result = self.script.pop(0)
        if result.get('action') != action:
            return {'status': 'unknown'}
        if action != 'READ_STATUS':
            # Simulated receiver-side conditional operation, NOT a real Android API.
            if result.get('status') in ('timeout', 'unknown'):
                entry['effect_applied'] = None
            elif result.get('status') == 'ok':
                guard = result.get('guard', {})
                required = {k: payload[k] for k in ('expected_boot', 'session_id', 'owner') if k in payload}
                if any(guard.get(k) != v for k, v in required.items()):
                    return {'status': 'failed'}
                if action == 'STOP_CAMERA' and guard.get('recording_active') is not True:
                    return {'status': 'failed'}
                if action == 'RESTORE_CAMERA' and guard.get('recording_active') is not False:
                    return {'status': 'failed'}
                entry['effect_applied'] = True
        return result


@dataclass(frozen=True)
class QualifiedReceipt:
    operation_id: str
    stage: str
    observed_at: float
    payload: dict


class RecoveryGate(ReadOnly):
    _snapshots = frozenset({"component", "incident", "route", "device", "max_age", "counter", "terminal", "receipts", "last_receipt"})
    _references = frozenset({"admission", "backend", "clock"})
    """Bridge to operation-bound custody admission; receipts have local custody.

    admission.authorize returns an exact-context approved synthetic decision,
    admission.record receives outcome. Adapter implements the real pure reducer.
    No externally constructed receipt, copied receipt or replay is accepted.
    """
    def __init__(self, *, component, incident, route, device, admission, backend,
                 clock, max_age=5):
        self._initialize_once()
        from custody_bridge import CustodyAdmission
        if type(admission) is not CustodyAdmission:
            raise Blocked('actual pure custody reducer bridge required')
        if type(backend) is not FakeBackend:
            raise Blocked('only literal FakeBackend is allowed')
        admission._claim_gate()
        self._controller_claimed = False
        self._component, self._incident, self._route, self._device = component, incident, route, device
        self._admission, self._backend, self._clock = admission, backend, clock
        self._max_age, self._counter = max_age, 0
        self._terminal = False
        self._receipts = {}

    def _call(self, action, stage, payload=None):
        if self._terminal:
            raise Blocked('gate terminal; no retry in this epoch')
        if action not in ACTIONS:
            self._terminal = True
            raise Blocked('prohibited action')
        self._counter += 1
        op = f'{self._incident}:{self._component}:{self._counter}:{stage}'
        binding = dict(action=action, operation_id=op, component=self._component,
                       incident=self._incident, route=self._route, device=self._device)
        try:
            decision = self._admission._authorize(binding, self._clock())
            if type(decision) is not dict or decision.get('admitted') is not True or decision.get('binding') != binding:
                raise Blocked('unqualified or mismatched custody decision')
            result = self._backend.dispatch(action, deepcopy(payload or {}))
            status = result.get('status', 'unknown')
            if status not in ('ok', 'failed', 'timeout', 'unknown'):
                status = 'unknown'
            self._admission._record(binding, status)
            if status != 'ok':
                raise Blocked('operation ' + status)
            if action == 'READ_STATUS':
                observed = result.get('observed_at')
                if type(observed) not in (float, int) or not isfinite(observed):
                    raise Blocked('missing observation time')
                data = result.get('payload', {})
                if data.get('physical_id') != self._device or data.get('boot_id') != decision.get('physical_boot'):
                    raise Blocked('observation not bound to admitted device/boot')
                receipt = QualifiedReceipt(op, stage, observed, deepcopy(data))
                self._receipts[op] = (receipt, deepcopy(data))
                return receipt
            return None
        except Exception:
            self._terminal = True
            raise

    def _consume(self, receipt, stage):
        try:
            if self._terminal or type(receipt) is not QualifiedReceipt:
                raise Blocked('receipt not issued by live gate')
            issued = self._receipts.pop(receipt.operation_id, None)
            if issued is None or issued[0] is not receipt or not exact(issued[1], receipt.payload):
                raise Blocked('receipt foreign, copied or replayed')
            if receipt.stage != stage:
                raise Blocked('receipt stage mismatch')
            now = self._clock()
            if not isfinite(now) or not 0 <= now-receipt.observed_at <= self._max_age:
                raise Blocked('receipt stale or future')
            self._last_receipt = receipt
            return deepcopy(receipt.payload)
        except Exception:
            self._terminal = True
            raise


class Controller(ReadOnly):
    _snapshots = frozenset({"original_failed_state", "state", "events", "failure", "identity", "old_boot", "new_boot", "original_settings", "reboot_attempted", "restore_attempted", "boot", "session", "owner", "media_id", "original_activity", "original_task", "profile", "settings", "stop_attempted"})
    _references = frozenset()
    @property
    def gate(self):
        # Diagnostic value only: no controller-owned gate/admission/backend handles.
        return {name: getattr(self._gate, name) for name in
                ('component', 'incident', 'route', 'device', 'counter', 'terminal')}

    def __init__(self, gate, original_failed_state):
        self._initialize_once()
        if gate._controller_claimed: raise ValueError("gate already has a controller")
        gate._controller_claimed = True
        self._gate = gate
        self._original_failed_state = deepcopy(original_failed_state)
        self._state = 'NEED_PRECHECK'
        self._events = []
        self._failure = None

    def _require(self, condition, why):
        if not condition:
            raise Blocked(why)

    def _transition(self, expected, fn):
        try:
            self._require(self._state == expected, 'out of order or terminal controller')
            fn()
            self._events.append(self._state)
        except Exception as exc:
            self._failure = str(exc)
            self._state = 'RECOVERY_FAILED'
            self._gate._terminal = True
            self._events.append(self._state)
            raise Blocked(self._failure) from exc

    def _observation(self, stage, receipt=None):
        if receipt is None:
            receipt = self._gate._call('READ_STATUS', stage)
        return self._gate._consume(receipt, stage)

    def _recent_guard(self):
        receipt = getattr(self._gate, 'last_receipt', None)
        self._require(receipt is not None and 0 <= self._gate.clock()-receipt.observed_at <= self._gate.max_age,
                     'pre-action semantic evidence expired')

    def summary(self):
        return dict(state=self._state, recovery_failed=self._state == 'RECOVERY_FAILED',
                    original_failed_state=deepcopy(self._original_failed_state),
                    events=list(self._events), failure=self._failure,
                    physical_admission=False, original_trial_status='unchanged', stock_admission='HOLD')


def boot_uuid(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


class TargetRecovery(Controller):
    def __init__(self, gate, original_failed_state, *, identity, old_boot, original_settings):
        super().__init__(gate, original_failed_state)
        if gate.component != 'target':
            raise Blocked('target controller requires target gate')
        self._identity = deepcopy(identity)
        self._old_boot, self._new_boot = old_boot, None
        self._original_settings = deepcopy(original_settings)
        if type(original_settings) is not dict or not {'screen_brightness_mode', 'screen_brightness', 'screen_off_timeout', 'native_dbv', 'logger'} <= set(original_settings):
            raise Blocked('complete original target snapshot required')
        self._reboot_attempted = self._restore_attempted = False

    def _check_identity(self, data):
        self._require(exact(data.get('identity'), self._identity), 'wrong exact target/module/panel identity')
        self._require(type(data.get('root_uid')) is int and data['root_uid'] == 0, 'root not independently verified')
        self._require(data.get('selinux') == 'Enforcing', 'SELinux not Enforcing')

    def precheck(self, receipt=None):
        def run():
            d = self._observation('target_precheck', receipt)
            self._check_identity(d)
            self._require(boot_uuid(self._old_boot) and d.get('boot_id') == self._old_boot, 'old boot mismatch')
            self._require(exact(d.get('original_snapshot'), self._original_settings), 'missing/mismatched captured originals')
            self._state = 'READY_REBOOT'
        self._transition('NEED_PRECHECK', run)

    def reboot(self):
        def run():
            self._recent_guard()
            self._require(not self._reboot_attempted, 'reboot already attempted')
            self._reboot_attempted = True  # unknown dispatch must never become retryable
            self._gate._call('REBOOT_TARGET', 'target_reboot', {'expected_boot': self._old_boot})
            self._state = 'NEED_CHANGED_BOOT'
        self._transition('READY_REBOOT', run)

    def changed_boot(self, receipt=None):
        def run():
            d = self._observation('target_changed_boot', receipt)
            self._check_identity(d)
            self._require(boot_uuid(d.get('boot_id')) and d['boot_id'] != self._old_boot, 'no verified changed boot')
            self._require(d.get('boot_completed') is True, 'boot incomplete')
            self._require(d.get('dc_stock_safe') is True and d.get('esd') == 'reg_read', 'DC/ESD unverified')
            self._new_boot = d['boot_id']
            self._gate.admission._confirm_reboot(self._old_boot, self._new_boot, self._gate.last_receipt.operation_id)
            self._state = 'READY_RESTORE'
        self._transition('NEED_CHANGED_BOOT', run)

    def restore(self):
        def run():
            self._recent_guard()
            self._require(not self._restore_attempted, 'restore already attempted')
            self._restore_attempted = True
            self._gate._call('RESTORE_TARGET', 'target_restore',
                           {'expected_boot': self._new_boot, 'original_settings': self._original_settings})
            self._state = 'NEED_RESTORED_READBACK'
        self._transition('READY_RESTORE', run)

    def restored(self, receipt=None):
        def run():
            d = self._observation('target_restored', receipt)
            self._check_identity(d)
            self._require(d.get('boot_id') == self._new_boot, 'restoration boot drift')
            self._require(d.get('dc_stock_safe') is True and d.get('esd') == 'reg_read', 'restored DC/ESD missing')
            self._require(exact(d.get('settings'), self._original_settings), 'original settings/DBV/logger not restored')
            self._require(d.get('power_verified') is True, 'power state unverified')
            self._state = 'VERIFIED_FAKE_COMPONENT'
        self._transition('NEED_RESTORED_READBACK', run)


class CameraRecovery(Controller):
    def __init__(self, gate, original_failed_state, *, identity, boot, session, owner,
                 media_id, original_activity, original_task, original_profile, original_settings):
        super().__init__(gate, original_failed_state)
        if gate.component != 'camera':
            raise Blocked('camera controller requires camera gate')
        self._identity, self._boot = deepcopy(identity), boot
        self._session, self._owner, self._media_id = session, owner, media_id
        self._original_activity, self._original_task = original_activity, original_task
        self._profile, self._settings = deepcopy(original_profile), deepcopy(original_settings)
        if type(original_profile) is not dict or not {'exposure_ns', 'iso', 'focus_diopters', 'ae_lock', 'awb_lock', 'zoom', 'camera_id', 'resolution', 'fps', 'audio'} <= set(original_profile):
            raise Blocked('complete original camera profile required')
        if type(original_settings) is not dict or not {'video_mode', 'restart_count', 'saf', 'duration_limit', 'size_limit'} <= set(original_settings):
            raise Blocked('complete original camera settings required')
        self._stop_attempted = self._restore_attempted = False

    def _check_session(self, d):
        self._require(exact(d.get('identity'), self._identity) and d.get('boot_id') == self._boot and boot_uuid(self._boot), 'camera identity/boot drift')
        self._require(d.get('session_id') == self._session and d.get('owner') == self._owner,
                     'foreign camera session or ownership')
        self._require(d.get('session_binding_verified') is True, 'session binding unqualified')

    def precheck(self, receipt=None):
        def run():
            d = self._observation('camera_precheck', receipt)
            self._check_session(d)
            self._require(d.get('recording_active') is True, 'stop requires verified active owned recording')
            self._require(d.get('stop_only_capability_verified') is True, 'no qualified non-toggle stop capability')
            self._state = 'READY_STOP'
        self._transition('NEED_PRECHECK', run)

    def stop(self):
        def run():
            self._recent_guard()
            self._require(not self._stop_attempted, 'camera stop already attempted')
            self._stop_attempted = True
            self._gate._call('STOP_CAMERA', 'camera_stop', {'session_id': self._session, 'owner': self._owner,
                                                        'expected_boot': self._boot})
            self._state = 'NEED_STOP_OBSERVATION'
        self._transition('READY_STOP', run)

    def stopped(self, receipt=None):
        def run():
            d = self._observation('camera_stopped', receipt)
            self._check_session(d)
            self._require(d.get('recording_active') is False and d.get('stop_observed') is True,
                         'callback/elapsed time/ack is not completed stop')
            self._state = 'NEED_MEDIA_FINALIZATION'
        self._transition('NEED_STOP_OBSERVATION', run)

    def finalized(self, receipt=None):
        def run():
            d = self._observation('camera_media', receipt)
            self._check_session(d)
            self._require(d.get('media_id') == self._media_id, 'foreign media')
            for key in ('finalized', 'original_retained', 'decode_valid', 'metadata_retained'):
                self._require(d.get(key) is True, 'media evidence missing: '+key)
            self._state = 'READY_PROFILE_RESTORE'
        self._transition('NEED_MEDIA_FINALIZATION', run)

    def restore(self):
        def run():
            self._recent_guard()
            self._require(not self._restore_attempted, 'camera restoration already attempted')
            self._restore_attempted = True
            self._gate._call('RESTORE_CAMERA', 'camera_restore',
                           {'expected_boot': self._boot, 'session_id': self._session, 'owner': self._owner,
                            'original_activity': self._original_activity, 'original_task': self._original_task,
                            'original_profile': self._profile, 'original_settings': self._settings})
            self._state = 'NEED_PROFILE_READBACK'
        self._transition('READY_PROFILE_RESTORE', run)

    def restored(self, receipt=None):
        def run():
            d = self._observation('camera_restored', receipt)
            self._check_session(d)
            self._require(d.get('recording_active') is False and d.get('idle_preview_verified') is True, 'camera not verified idle')
            self._require(d.get('activity') == self._original_activity and d.get('task') == self._original_task,
                         'original A/task not restored')
            self._require(exact(d.get('profile'), self._profile), 'focus/exposure/locks/full profile mismatch')
            self._require(exact(d.get('settings'), self._settings), 'original camera settings mismatch')
            self._state = 'VERIFIED_FAKE_COMPONENT'
        self._transition('NEED_PROFILE_READBACK', run)


def joint_result(target, camera):
    summaries = {'target': target.summary(), 'camera': camera.summary()}
    failed = any(v['recovery_failed'] for v in summaries.values())
    complete = all(v['state'] == 'VERIFIED_FAKE_COMPONENT' for v in summaries.values())
    return dict(components=summaries, recovery_failed=failed,
                status='recovery_failed' if failed else ('fake_components_verified' if complete else 'pending'),
                physical_admission=False, stock_admission='HOLD', old_adapter='terminal',
                watchdog60_600_proves_camera_stop=False)
