"""Pure fake-evidence model. NO readers, transport, dispatch or production authority.
Evidence authenticity/reader qualification is an external premise, not a bool proof.
"""
from dataclasses import dataclass, fields, replace
from enum import Enum

class Hop(Enum):
    CLIENT_FORWARD = 'client_forward'
    SSH_SESSION = 'ssh_session'
    REMOTE_ADB = 'remote_adb'
    TRANSPORT_DEVICE = 'transport_device'

class Capability(Enum):
    PROC_SNAPSHOT = 'proc_snapshot'
    EXE_SNAPSHOT = 'exe_snapshot'
    HOLDER_SNAPSHOT = 'holder_snapshot'
    TRANSPORT_BINDING_SNAPSHOT = 'transport_binding_snapshot'
    PIDFD_LIVE = 'pidfd_live'
    EXEC_CONTINUITY = 'exec_continuity'
    HELD_CHANNEL = 'held_channel'
    CUSTODY_CONTINUITY = 'custody_continuity'
    UNIX_PEERCRED = 'unix_peercred'
    SSH_AUTH = 'ssh_auth'
    PHYSICAL_SNAPSHOT = 'physical_snapshot'
    TRANSPORT_PHYSICAL_CONTINUITY = 'transport_physical_continuity'

class Fault(Enum):
    NONE = 'none'
    CUSTODY_GAP = 'custody_gap'
    NEW_HOLDER = 'new_holder'
    EXEC = 'exec'
    TASK_EXIT = 'task_exit'
    SERVER_REPLACED = 'server_replaced'
    TRANSPORT_REUSED = 'transport_reused'
    UNTRUSTED_RECONNECT = 'untrusted_reconnect'
    DENIED = 'denied'
    UNKNOWN = 'unknown'

class IncidentCause(Enum):
    VERIFIED_NONSERVER_EXIT = 'verified_nonserver_exit'
    DENIAL = 'denial'
    UNRESOLVED = 'unresolved'

class Action(Enum):
    READ_STATUS = 'read_status'
    REBOOT_TARGET = 'reboot_target'
    RESTORE_TARGET = 'restore_target'
    STOP_CAMERA = 'stop_camera'
    RESTORE_CAMERA = 'restore_camera'
    RELEASE_OWNER = 'release_owner'

class Component(Enum):
    TARGET = 'target'
    CAMERA = 'camera'

class Outcome(Enum):
    SUCCESS = 'success'
    DENIED = 'denied'
    UNKNOWN = 'unknown'

@dataclass(frozen=True)
class Domain:
    host: str
    boot: str
    clock: str  # explicit native monotonic clock, never wall time

@dataclass(frozen=True)
class Binding:
    source_digest: str
    machine_boot: str
    task_token: str  # PID-object/process binding, NOT immutable task_struct/exe
    executable_token: str  # dev/inode/content + exec epoch, NOT just open old exe fd
    socket_token: str  # endpoint/socket/connection identity, NOT reusable FD number
    namespace_token: str
    ssh_session: str
    server_epoch: str
    transport_id: str
    physical_id: str
    physical_boot: str

@dataclass(frozen=True)
class HopContract:
    hop: Hop
    domain: Domain
    since_ns: int
    expected: Binding

@dataclass(frozen=True)
class Qualification:
    reader_id: str
    reader_source_digest: str
    qualification_id: str
    hop: Hop
    domain: Domain
    capabilities: frozenset

@dataclass(frozen=True)
class Observation:
    hop: Hop
    domain: Domain
    start_ns: int
    end_ns: int
    binding: Binding
    capability: Capability
    reader_id: str
    reader_source_digest: str
    qualification_id: str
    capture_digest: str
    sequence: int
    evidence_nonce: str
    fault: Fault = Fault.NONE

@dataclass(frozen=True)
class RouteContract:
    incident: str
    route_id: str
    source_digest: str
    component: Component
    physical_id: str
    physical_boot: str
    independent_review_id: str
    evidence_nonce: str
    hops: tuple
    qualifications: tuple
    max_snapshot_age_ns: int

@dataclass(frozen=True)
class HopVerdict:
    hop: Hop
    task_lifetime: bool
    executable_snapshot: bool
    connection_lifetime: bool
    holder_snapshot: bool
    continuous_custody: bool
    physical_identity: bool
    reasons: tuple

@dataclass(frozen=True)
class RouteVerdict:
    contract: RouteContract
    observations: tuple
    now_by_domain: tuple
    hops: tuple
    admitted_model_only: bool
    reasons: tuple

@dataclass(frozen=True)
class Request:
    incident: str
    route_id: str
    evidence_nonce: str
    operation_id: str
    component: Component
    physical_id: str
    action: Action

@dataclass(frozen=True)
class Authority:
    request: Request
    independent_recovery_approval_id: str

@dataclass(frozen=True)
class RecoveryState:
    incident: str
    source_digest: str
    old_route_id: str
    old_adapter_terminal: bool
    queue_uncertain: bool
    original_target_boot: str
    incident_cause: IncidentCause = IncidentCause.UNRESOLVED
    incident_explanation_id: str = ''
    consumed_operations: frozenset = frozenset()
    pending: object = None
    terminal_reason: str = ''
    consumed_evidence: frozenset = frozenset()

@dataclass(frozen=True)
class RebootProof:
    incident: str
    physical_id: str
    old_boot: str
    new_boot: str
    verification_receipt: str
    boot_completed: bool
    identity_root_enforcing_module_panel_stock: bool

@dataclass(frozen=True)
class Decision:
    request: Request
    admitted_model_only: bool
    reasons: tuple
    source_digest: str = ''


def digest(v):
    return type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)

def ident(v):return type(v) is str and 0<len(v)<=256

def integer(v):return type(v) is int and 0<=v<2**63

def domain_ok(d):
    return type(d) is Domain and all(ident(getattr(d,k)) for k in ('host','boot','clock')) and d.clock=='monotonic_ns'

def binding_ok(b):
    return type(b) is Binding and digest(b.source_digest) and all(ident(getattr(b,f.name)) for f in fields(b) if f.name!='source_digest')

def route_contract_ok(c):
    if type(c) is not RouteContract:return False
    if not all(ident(getattr(c,k)) for k in ('incident','route_id','physical_id','physical_boot','independent_review_id','evidence_nonce')) or not digest(c.source_digest):return False
    if type(c.component) is not Component or type(c.hops) is not tuple or type(c.qualifications) is not tuple or not integer(c.max_snapshot_age_ns):return False
    if tuple(h.hop if type(h) is HopContract else None for h in c.hops)!=tuple(Hop):return False
    for h in c.hops:
        if not domain_ok(h.domain) or not integer(h.since_ns) or not binding_ok(h.expected):return False
        if h.expected.machine_boot!=h.domain.boot or h.expected.source_digest!=c.source_digest:return False
    last=c.hops[-1].expected
    if last.physical_id!=c.physical_id or last.physical_boot!=c.physical_boot:return False
    for q in c.qualifications:
        if type(q) is not Qualification or type(q.hop) is not Hop or not domain_ok(q.domain):return False
        if not all(ident(getattr(q,k)) for k in ('reader_id','qualification_id')) or not digest(q.reader_source_digest):return False
        if type(q.capabilities) is not frozenset or not q.capabilities or any(type(v) is not Capability for v in q.capabilities):return False
    return True


def assess_route(contract, evidence, now_by_domain):
    """Tuple[(Domain, now_ns)] only: each hop uses its own clock; no cross-host math.
    Reader identity/capabilities must match externally qualified fixed config. This
    cannot authenticate attacker-controlled receipts or qualify its own collector.
    """
    reasons=[]; verdicts=[]
    def result():return RouteVerdict(contract,evidence,now_by_domain,tuple(verdicts),not reasons,tuple(reasons))
    if not route_contract_ok(contract) or type(evidence) is not tuple or type(now_by_domain) is not tuple:
        reasons.append('malformed_contract_or_container');return result()
    if any(type(x) is not tuple or len(x)!=2 or not domain_ok(x[0]) or not integer(x[1]) for x in now_by_domain):
        reasons.append('invalid_clock');return result()
    clocks=dict(now_by_domain)
    if len(clocks)!=len(now_by_domain) or set(clocks)!={h.domain for h in contract.hops}:
        reasons.append('missing_duplicate_or_extra_clock_domain');return result()
    seen=set();last_sequences={}
    for e in evidence:
        if type(e) is not Observation or type(e.hop) is not Hop or type(e.capability) is not Capability or type(e.fault) is not Fault:
            reasons.append('malformed_observation');continue
        if not domain_ok(e.domain) or not binding_ok(e.binding) or not integer(e.start_ns) or not integer(e.end_ns) or e.start_ns>e.end_ns or not integer(e.sequence):
            reasons.append('malformed_observation_values');continue
        if not digest(e.capture_digest) or not digest(e.reader_source_digest) or not ident(e.reader_id) or not ident(e.qualification_id):reasons.append('missing_provenance')
        if e.evidence_nonce!=contract.evidence_nonce:reasons.append('wrong_capture_epoch')
        key=(e.reader_id,e.hop,e.domain)
        if key in last_sequences and e.sequence<=last_sequences[key]:reasons.append('reordered_or_replayed_evidence')
        last_sequences[key]=e.sequence
        unique=(e.reader_id,e.hop,e.sequence,e.capture_digest)
        if unique in seen:reasons.append('duplicate_evidence')
        seen.add(unique)
        h=next(x for x in contract.hops if x.hop is e.hop)
        if e.domain!=h.domain or e.binding!=h.expected:reasons.append('stale_or_changed_hop_binding:'+e.hop.value)
        elif e.end_ns>clocks[h.domain] or e.start_ns<h.since_ns:reasons.append('out_of_epoch_evidence')
        if not any(q.reader_id==e.reader_id and q.reader_source_digest==e.reader_source_digest and q.qualification_id==e.qualification_id and q.hop is e.hop and q.domain==e.domain and e.capability in q.capabilities for q in contract.qualifications):reasons.append('unqualified_reader_capability')
        if e.fault is not Fault.NONE:reasons.append('terminal_evidence_fault:'+e.fault.value)
    # Invalid records never contribute even partial positive evidence.
    if reasons:return result()
    for h in contract.hops:
        now=clocks[h.domain];es=tuple(e for e in evidence if e.hop is h.hop)
        local=[]
        if now<h.since_ns:local.append('clock_before_epoch')
        def covers(cap):
            intervals=sorted((e.start_ns,e.end_ns) for e in es if e.capability is cap)
            if not intervals:return False
            cursor=h.since_ns
            for a,b in intervals:
                if a>cursor:return False
                cursor=max(cursor,b)
            return cursor==now and now>=h.since_ns
        def fresh(cap):return any(e.capability is cap and now-e.end_ns<=contract.max_snapshot_age_ns for e in es)
        task=covers(Capability.PIDFD_LIVE)
        exe=fresh(Capability.EXE_SNAPSHOT)
        channel=covers(Capability.HELD_CHANNEL)
        holder=fresh(Capability.HOLDER_SNAPSHOT)
        continuous=covers(Capability.CUSTODY_CONTINUITY) and covers(Capability.EXEC_CONTINUITY)
        if h.hop is Hop.SSH_SESSION:channel=channel and fresh(Capability.SSH_AUTH)
        physical=(fresh(Capability.PHYSICAL_SNAPSHOT) and fresh(Capability.TRANSPORT_BINDING_SNAPSHOT)) if h.hop is Hop.TRANSPORT_DEVICE else False
        if not task:local.append('task_lifetime_unproved')
        if not exe:local.append('executable_snapshot_unproved')
        if not channel:local.append('connection_lifetime_unproved')
        if not holder:local.append('original_scoped_holder_snapshot_unproved')
        if h.hop is Hop.TRANSPORT_DEVICE and not physical:local.append('physical_identity_unproved')
        verdicts.append(HopVerdict(h.hop,task,exe,channel,holder,continuous,physical,tuple(local)))
        reasons.extend(h.hop.value+':'+x for x in local)
    return result()


def state_ok(s):
    return (type(s) is RecoveryState and ident(s.incident) and digest(s.source_digest)
        and ident(s.old_route_id) and s.old_adapter_terminal is True
        and type(s.queue_uncertain) is bool and ident(s.original_target_boot)
        and type(s.incident_cause) is IncidentCause and type(s.incident_explanation_id) is str
        and type(s.consumed_operations) is frozenset and all(ident(x) for x in s.consumed_operations)
        and (s.pending is None or type(s.pending) is Request) and type(s.terminal_reason) is str
        and type(s.consumed_evidence) is frozenset and all(ident(x) for x in s.consumed_evidence))

def request_ok(r):
    return type(r) is Request and type(r.component) is Component and type(r.action) is Action and all(ident(getattr(r,k)) for k in ('incident','route_id','evidence_nonce','operation_id','physical_id'))


def admit(state, request, authority, route, verified_reboot=None, *, dispatch_now_by_domain):
    """No dispatch. Returns one-shot fictional reservation, never actual authority."""
    reasons=[]
    if not state_ok(state) or not request_ok(request):return state,Decision(request,False,('malformed_state_or_request',))
    if state.terminal_reason or state.pending is not None:reasons.append('epoch_terminal_or_pending')
    if state.incident_cause is not IncidentCause.VERIFIED_NONSERVER_EXIT or not ident(state.incident_explanation_id):reasons.append('denied_or_unresolved_incident')
    if request.operation_id in state.consumed_operations:reasons.append('operation_already_consumed')
    if request.evidence_nonce in state.consumed_evidence:reasons.append('evidence_epoch_already_consumed')
    if request.route_id==state.old_route_id:reasons.append('old_adapter_route_terminal')
    if request.incident!=state.incident:reasons.append('incident_mismatch')
    if type(authority) is not Authority or authority.request!=request or not ident(authority.independent_recovery_approval_id):reasons.append('missing_exact_recovery_authority')
    if type(route) is not RouteVerdict:reasons.append('no_route_evidence')
    else:
        checked=assess_route(route.contract,route.observations,dispatch_now_by_domain)
        if checked!=route or checked.admitted_model_only is not True:reasons.append('unverified_or_forged_route_verdict')
        c=route.contract
        if not route_contract_ok(c) or (c.incident,c.route_id,c.evidence_nonce,c.component,c.physical_id,c.source_digest)!=(request.incident,request.route_id,request.evidence_nonce,request.component,request.physical_id,state.source_digest):reasons.append('route_request_binding_mismatch')
    if request.action in (Action.REBOOT_TARGET,Action.RESTORE_TARGET) and request.component is not Component.TARGET:reasons.append('wrong_component')
    if request.action in (Action.STOP_CAMERA,Action.RESTORE_CAMERA) and request.component is not Component.CAMERA:reasons.append('wrong_component')
    if state.queue_uncertain and request.component is Component.TARGET and request.action in (Action.RESTORE_TARGET,Action.RELEASE_OWNER):
        p=verified_reboot
        if not (type(p) is RebootProof and p.incident==state.incident and p.physical_id==request.physical_id
                and p.old_boot==state.original_target_boot and ident(p.new_boot) and p.new_boot!=p.old_boot
                and type(route) is RouteVerdict and p.new_boot==route.contract.physical_boot
                and ident(p.verification_receipt) and p.boot_completed is True
                and p.identity_root_enforcing_module_panel_stock is True):reasons.append('same_target_reboot_unverified')
    if reasons:
        # A failed route assessment sticks in this model epoch. A later clean
        # snapshot cannot erase unknown/denial/custody uncertainty. No retry.
        if any(x in reasons for x in ('no_route_evidence','unverified_or_forged_route_verdict','route_request_binding_mismatch')):
            state=replace(state,terminal_reason=state.terminal_reason or 'terminal_route_assessment')
        return state,Decision(request,False,tuple(reasons))
    new=RecoveryState(state.incident,state.source_digest,state.old_route_id,True,state.queue_uncertain,state.original_target_boot,state.incident_cause,state.incident_explanation_id,state.consumed_operations|{request.operation_id},request,'',state.consumed_evidence|{request.evidence_nonce})
    return new,Decision(request,True,(),state.source_digest)


def complete(state, request, outcome):
    """Reboot request SUCCESS is only request completion, never verified reboot."""
    if not state_ok(state) or not request_ok(request) or state.pending!=request or type(outcome) is not Outcome:
        raise ValueError('No matching pending operation and typed outcome')
    reason=state.terminal_reason if outcome is Outcome.SUCCESS else 'terminal_completion:'+outcome.value
    return RecoveryState(state.incident,state.source_digest,state.old_route_id,True,state.queue_uncertain,state.original_target_boot,state.incident_cause,state.incident_explanation_id,state.consumed_operations,None,reason,state.consumed_evidence)
