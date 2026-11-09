from readonly import ReadOnly
"""Adapter to sibling pure per-hop model; no host/device or process reader."""
import importlib.util
from pathlib import Path
import sys
import hashlib

MODEL_PATH = Path(__file__).resolve().parents[2] / '06-tools/recovery_hop_custody_20261109/custody_model.py'
MODEL_SHA256 = 'bd15667991aa29e516ed14e4186215025b123a18bc79ebb49e8776cc04a8d953'
model_source = MODEL_PATH.read_bytes()
if hashlib.sha256(model_source).hexdigest() != MODEL_SHA256:
    raise RuntimeError('offline custody dependency differs from reviewed fixture source')
spec = importlib.util.spec_from_file_location('offline_recovery_custody_model', MODEL_PATH)
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
exec(compile(model_source, str(MODEL_PATH), 'exec'), model.__dict__)


class CustodyAdmission(ReadOnly):
    _snapshots = frozenset({"state", "pending", "decisions", "verified_reboot"})
    """Consumes actual reducer decisions; supplier is explicit synthetic evidence.

    Supplier is NOT a qualified physical collector. No actual backend exists;
    model booleans never become authentication or physical authority.
    """
    def __init__(self, state, route_supplier, authority_supplier):
        self._initialize_once()
        if state.consumed_operations or state.consumed_evidence or state.pending is not None or state.terminal_reason:
            raise ValueError("cannot reconstruct admission from used state")
        self._gate_claimed = False
        self._state = state
        self._route_supplier = route_supplier
        self._authority_supplier = authority_supplier
        self._pending = {}
        self._decisions = []
        self._verified_reboot = None

    def _authorize(self, binding, now):
        contract, evidence, clocks = self._route_supplier(binding, now)
        verdict = model.assess_route(contract, evidence, clocks)
        request = model.Request(binding['incident'], binding['route'], contract.evidence_nonce,
                                binding['operation_id'], model.Component(binding['component']),
                                binding['device'], model.Action(binding['action'].lower()))
        authority = self._authority_supplier(request)
        self._state, decision = model.admit(self._state, request, authority, verdict,
                            self._verified_reboot, dispatch_now_by_domain=clocks)
        self._decisions.append(decision)
        if decision.admitted_model_only:
            self._pending[request.operation_id] = request
        return dict(admitted=decision.admitted_model_only, binding=dict(binding),
                    physical_boot=contract.physical_boot, reasons=decision.reasons,
                    physical_authority=False)

    def _record(self, binding, status):
        request = self._pending.pop(binding['operation_id'])
        outcome = model.Outcome.SUCCESS if status == 'ok' else (
            model.Outcome.DENIED if status == 'failed' else model.Outcome.UNKNOWN)
        self._state = model.complete(self._state, request, outcome)

    def _confirm_reboot(self, old_boot, new_boot, observation_receipt):
        # Called only after TargetRecovery strict changed-boot/identity/state checks.
        prior = next((d for d in reversed(self._decisions)
                      if d.request.operation_id == observation_receipt and d.admitted_model_only), None)
        if prior is None or prior.request.action is not model.Action.READ_STATUS:
            raise ValueError('no admitted changed-boot read receipt')
        self._verified_reboot = model.RebootProof(prior.request.incident, prior.request.physical_id,
                              old_boot, new_boot, observation_receipt, True, True)

    def _claim_gate(self):
        if self._gate_claimed: raise ValueError("admission already bound to a gate")
        self._gate_claimed = True
